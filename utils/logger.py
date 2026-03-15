import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_structured_logging(level=logging.INFO):
    """
    Configures the root logger to output structured JSON logs.
    This should be called as early as possible in the application startup.
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicate logs if called multiple times
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    log_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
        rename_fields={
            "levelname": "level",
            "asctime": "timestamp",
        }
    )
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)

    # Prevent basicConfig from overriding our setup
    logging.basicConfig = lambda *args, **kwargs: None
