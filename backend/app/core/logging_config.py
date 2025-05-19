import logging
import sys
import os
from .config import settings


def setup_logging():
    """
    Configures the root logger for the application.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Remove existing handlers to avoid duplicates if called multiple times
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stream handler (console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    logging.basicConfig(level=numeric_level, handlers=[stream_handler])

    # Set log levels for noisy libraries if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info(
        f"Logging configured at level {log_level} for project {settings.PROJECT_NAME}."
    )
