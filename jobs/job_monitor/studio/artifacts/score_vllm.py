import logging
import os
import shlex
import subprocess
import time
import argparse
import json
from typing import AsyncGenerator
from urllib.parse import urlparse

from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.sampling_params import SamplingParams
from vllm.utils import random_uuid
from functools import lru_cache

import ads
from ads.common.utils import copy_from_uri
from ads.model.generic_model import GenericModel


os.environ["CRYPTOGRAPHY_OPENSSL_NO_LEGACY"] = "1"
ads.set_auth("resource_principal")

TIMEOUT_KEEP_ALIVE = 5  # seconds.
TIMEOUT_TO_PREVENT_DEADLOCK = 1  # seconds.

engine = None

def run_command(
    command: str, conda_prefix: str = None, level=None, check=False
) -> int:
    """Runs a shell command and logs the outputs with specific log level.

    Parameters
    ----------
    command : str
        The shell command
    conda_prefix : str, optional
        Prefix of the conda environment for running the command.
        Defaults to None.
    level : int, optional
        Logging level for the command outputs, by default None.
        If this is set to a log level from logging, e.g. logging.DEBUG,
        the command outputs will be logged with the level.
        If this is None, the command outputs will be printed.

    Returns
    -------
    int
        The return code of the command.
    """
    # Add a small time delay so the existing outputs will not intersect with the command outputs.
    logger = logging.getLogger(__name__)
    time.sleep(0.05)
    logger.info(">>> %s", command)
    cmd = command
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        shell=True,
    )
    # Stream the outputs
    logger.debug("Streaming command output from subprocess %s", process.pid)
    while True:
        output = process.stdout.readline()
        if process.poll() is not None and output == b"":
            break
        if output:
            msg = output.decode()
            if level is None:
                # output already contains the line break
                print(msg, flush=True, end="")
            else:
                # logging will flush outputs by default
                # logging will add line break
                msg = msg.rstrip("\n")
                logger.log(level=level, msg=msg)
        # Add a small delay so that
        # outputs from the subsequent code will have different timestamp for oci logging
        time.sleep(0.02)
    logger.debug(
        "subprocess %s returned exit code %s", process.pid, process.returncode
    )
    if check and process.returncode != 0:
        # If there is an error, exit the main process with the same return code.
        sys.exit(process.returncode)
    return process.returncode


def download_model():
    # run_command("pip freeze")
    run_command("conda-unpack")
    temp_artifact_dir = "/home/datascience/temp"
    os.makedirs(temp_artifact_dir, exist_ok=True)
    os.environ["OCIFS_IAM_TYPE"] = "resource_principal"
    deployed_model = GenericModel.from_model_deployment(
        model_deployment_id=os.environ["MODEL_DEPLOYMENT_OCID"],
        artifact_dir=temp_artifact_dir
    )
    model_file_uri = deployed_model.metadata_custom["model_path"].value
    model_file_dir = "/home/datascience/model"
    os.makedirs(model_file_dir)
    print(f"Downloading model from {model_file_uri}...")
    copy_from_uri(model_file_uri, model_file_dir, force_overwrite=True)
    print(f"Model downloaded to {model_file_dir}")
    return model_file_dir


#Reference - https://github.com/vllm-project/vllm/blob/main/vllm/entrypoints/api_server.py
@lru_cache(maxsize=1)
def load_model():
    if "MODEL_DEPLOYMENT_OCID" in os.environ:
        model_file_dir = download_model()
    else:
        model_file_dir = os.environ["MODEL_DIR"]
    parser = argparse.ArgumentParser()
    parser = AsyncEngineArgs.add_cli_args(parser)
    # start_args = os.environ.get("VLLM_PARAM", "")
    start_args = f"--model {model_file_dir} --tensor-parallel-size 2 --dtype half"
    print(f"VLLM ARGS: {start_args}")
    args = parser.parse_args(shlex.split(start_args))
    print(f"Checking what is inside {args.model}")
    try:
        print(os.listdir(args.model))
    except Exception as e:
        import traceback
        traceback.print_exc()
    print(f".........................")
    engine_args = AsyncEngineArgs.from_cli_args(args)
    engine = AsyncLLMEngine.from_engine_args(engine_args)
    return engine

async def predict_async(request_dict, model):
    """Generate completion for the request.

    The request should be a JSON object with the following fields:
    - prompt: the prompt to use for the generation.
    - stream: whether to stream the results or not.
    - other fields: the sampling parameters (See `SamplingParams` for details).
    """
    prompt = request_dict.pop("prompt")
    stream = request_dict.pop("stream", False)
    # model is not used here, but it is used in the LangChain vllm integration.
    request_dict.pop("model", None)
    sampling_params = SamplingParams(**request_dict)
    request_id = random_uuid()
    engine = model

    results_generator = engine.generate(prompt, sampling_params, request_id)


    final_output = None
    async for request_output in results_generator:
        final_output = request_output

    assert final_output is not None
    prompt = final_output.prompt
    text_outputs = [output.text for output in final_output.outputs]
    ret = {"text": text_outputs}
    print("inside async predict...")
    print(ret)
    return ret

def predict(data, model=load_model()):
    print("Running predict()...")
    request_dict = data
    import asyncio
    response = []
    async def predict_helper(request_dict, model):
        res = await predict_async(request_dict, model)
        response.append(res)
    coroutine = predict_helper(request_dict, model)
    asyncio.run(coroutine)
    print("Finishing predict()...")
    print(response[0])
    return response[0]