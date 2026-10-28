import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from src.config import config, BASE_DIR

def setup_logging():
    log_level_str = config.get("logging", "level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_file = config.get("logging", "file", "logs/bubbles.log")
    log_path = BASE_DIR / log_file

    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5*1024*1024, backupCount=3
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()
