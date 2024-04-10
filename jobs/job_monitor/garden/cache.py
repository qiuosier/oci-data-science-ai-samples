import json
import logging
import os


logger = logging.getLogger(__name__)


class CacheKeeper:

    PREFIX = ""

    def __init__(self, cache_location=None) -> None:
        if cache_location is None:
            if self.PREFIX:
                cache_location = os.path.join(".cache", self.PREFIX)
            else:
                cache_location = ".cache"
        if not os.path.exists(cache_location):
            os.makedirs(cache_location)
        self.cache_location = cache_location

    def _get_cache_path(self, ocid):
        return os.path.join(self.cache_location, f"{ocid}.json")

    def save_to_cache(self, ocid, context):
        cache_file = self._get_cache_path(ocid)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(context, f)

    def get_from_cache(self, ocid):
        cache_file = self._get_cache_path(ocid)
        if os.path.exists(cache_file):
            logger.debug("Getting from cache for %s", ocid)
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_from_service(self, ocid):
        raise NotImplementedError()

    def get(self, ocid):
        context = self.get_from_cache(ocid)
        if context is None:
            context = self.get_from_service(ocid)
            if context.get("stopped"):
                self.save_to_cache(ocid, context)
        return context
