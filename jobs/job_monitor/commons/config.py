import json
import os
from flask import request


from commons.auth import load_profiles, get_authentication


CONFIG_FILE_PATH = os.path.expanduser("~/.oci/config.json")
CONST_SERVICE_ENDPOINT = "service_endpoint"
CONST_YAML_DIR = "yaml_dir"
CONST_OVERRIDE_TENANCY = "override_tenancy"


class ConfigMap:
    def __init__(self, config_path=CONFIG_FILE_PATH) -> None:
        self.configs = load_profiles()
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                custom_configs = json.load(f)
            for k, v in custom_configs.items():
                config = self.configs.get(k, {})
                config.update(v)
                self.configs[k] = config

    def get(self, profile=None) -> dict:
        if not profile:
            profile = request.args.get("profile")
        config = self.configs.get(profile, {})
        config["profile"] = profile
        return config


CONFIG_MAP = ConfigMap()


def get_config():
    return CONFIG_MAP.get()


def get_tenancy_ocid(auth=None):
    # Tenancy ID from GET parameters
    tenancy_id = request.args.get("t")
    if tenancy_id:
        return tenancy_id
    # Tenancy ID from custom config
    config = get_config()
    if config.get(CONST_OVERRIDE_TENANCY):
        return config[CONST_OVERRIDE_TENANCY]
    # Tenancy ID from OCI auth
    if not auth:
        auth = get_authentication()
    if auth["config"]:
        if "TENANCY_OCID" in os.environ:
            tenancy_id = os.environ["TENANCY_OCID"]
        elif "override_tenancy" in auth["config"]:
            tenancy_id = auth["config"]["override_tenancy"]
        else:
            tenancy_id = auth["config"]["tenancy"]
    else:
        tenancy_id = getattr(auth["signer"], "tenancy_id", None)
    return tenancy_id
