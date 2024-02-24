import logging
import os


# Config logging
if "LOG_LEVEL" in os.environ and hasattr(logging, os.environ["LOG_LEVEL"]):
    LOG_LEVEL = getattr(logging, os.environ["LOG_LEVEL"])
else:
    LOG_LEVEL = logging.INFO
flask_log = logging.getLogger("werkzeug")
flask_log.setLevel(LOG_LEVEL)
logging.lastResort.setLevel(LOG_LEVEL)
logging.getLogger("telemetry").setLevel(LOG_LEVEL)
logger = logging.getLogger("app")
logger.setLevel(LOG_LEVEL)
