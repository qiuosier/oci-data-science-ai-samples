#!/usr/bin/env python
# -*- coding: utf-8 -*--

# Copyright (c) 2020, 2022 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/

"""Job artifact script for downloading the model from HuggingFace.

Set the HUGGING_FACE_HUB_TOKEN environment variable if it is required to access the model.
"""
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def download_model(model_name: str, to_dir: str):
    """Downloads the model from HuggingFace to local directory."""
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        return_dict=True,
        torch_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model.save_pretrained(to_dir)
    tokenizer.save_pretrained(to_dir)


def main():
    if len(sys.argv) != 3:
        raise ValueError(
            "Exactly 2 arguments are needed for this script: "
            "python download_model.py MODEL_NAME LOCAL_DIR"
        )
    model_name = sys.argv[1]
    to_dir = sys.argv[2]
    download_model(model_name, to_dir)


if __name__ == "__main__":
    main()
