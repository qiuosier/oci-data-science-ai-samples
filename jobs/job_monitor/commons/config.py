import json
import os
from flask import request


from commons.auth import load_profiles
from commons.errors import abort_with_json_error


CONFIG_FILE_PATH = os.path.expanduser("~/.oci/config.json")


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

    def get(self, profile=None):
        if not profile:
            profile = request.args.get(profile)
        if not profile:
            abort_with_json_error(400, "Profile not specified.")
        return self.configs.get(profile, {})


CONFIG_MAP = ConfigMap()
