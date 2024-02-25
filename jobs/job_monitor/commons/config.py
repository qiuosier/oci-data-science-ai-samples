import json
import os

import configparser
import oci
from flask import request, session


CONFIG_FILE_PATH = os.path.expanduser("~/.oci/config.json")
CONST_SERVICE_ENDPOINT = "service_endpoint"
CONST_YAML_DIR = "yaml_dir"
CONST_OVERRIDE_TENANCY = "override_tenancy"


def load_profiles(file_location=oci.config.DEFAULT_LOCATION):
    expanded_file_location = oci.config._get_config_path_with_fallback(file_location)

    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(expanded_file_location):
        raise oci.exceptions.ConfigFileNotFound(
            f"Could not find config file at {expanded_file_location}, "
            "please follow the instructions in the link to setup the config file "
            "https://docs.cloud.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm"
        )
    return {key: dict(parser[key]) for key in parser.keys()}


class ConfigMap:
    def __init__(self, config_path=CONFIG_FILE_PATH) -> None:
        try:
            self.configs = load_profiles()
        except oci.exceptions.ConfigFileNotFound:
            self.configs = {}

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                custom_configs = json.load(f)
            for k, v in custom_configs.items():
                config = self.configs.get(k, {})
                config.update(v)
                self.configs[k] = config

    def get(self, profile=None) -> dict:
        if not profile:
            profile = self.get_profile()
        config = self.configs.get(profile, {})
        config["profile"] = profile
        return config

    def get_profile(self):
        profile = request.args.get("profile")
        if profile:
            return profile

        if "profile" in session:
            return session["profile"]
        elif self.configs.keys():
            session["profile"] = list(self.configs.keys())[0]
            return session["profile"]
        else:
            return None


CONFIG_MAP = ConfigMap()


def get_config(profile=None):
    """Get custom configurations"""
    return CONFIG_MAP.get(profile)


def get_endpoint(profile=None):
    """Get service endpoint"""
    return get_config(profile).get(CONST_SERVICE_ENDPOINT)
