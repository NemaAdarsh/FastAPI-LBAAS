import logging
from pythonjsonlogger import jsonlogger
from .config import settings

def setup_logging():
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(env)s %(service)s'
    )
    logHandler.setFormatter(formatter)
    logger = logging.getLogger("lbaas")
    logger.setLevel(settings.LOG_LEVEL)
    logger.handlers = [logHandler]
    logger.propagate = False
    return logger

logger = setup_logging()