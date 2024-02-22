#!/usr/bin/env python
# -*- coding: utf-8 -*--

# Copyright (c) 2020, 2022 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/

"""Job artifact script for downloading the model from HuggingFace.
https://huggingface.co/docs/huggingface_hub/guides/download#download-an-entire-repository
Set the HUGGING_FACE_HUB_TOKEN environment variable if it is required to access the model.
"""
import json
import os
import sys
from huggingface_hub import snapshot_download


def main():
    if len(sys.argv) != 3:
        raise ValueError(
            "Exactly 2 arguments are needed for this script: "
            "python download_model.py MODEL_NAME LOCAL_DIR"
        )
    model_name = sys.argv[1]
    local_dir = sys.argv[2]
    print(f"Caching model {model_name} to local...")
    retry = 0
    while True:
        try:
            snapshot_download(repo_id=model_name, resume_download=True)
            break
        except:
            retry += 1
            if retry < 10:
                continue
            raise
    print(f"Model {model_name} Cached.")

    print(f"Moving model to {local_dir}...")
    os.makedirs(local_dir, exist_ok=True)
    snapshot_download(
        repo_id=model_name, local_dir=local_dir, local_dir_use_symlinks=False
    )

    print(f"Downloaded model {model_name} to {local_dir}.")

    # with open(os.path.join(local_dir, "oci_download.json"), 'w', encoding='utf-8') as f:
    #     json.dump({
    #         "job_ocid": os.environ.get("JOB_OCID"),
    #         "job_run_ocid": os.environ.get("JOB_RUN_OCID"),
    #         "done": True
    #     }, f)


if __name__ == "__main__":
    main()
