"""Structured JSON logging for the SINAN agent."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "sinan_agent.log")


def get_logger(name: str = "sinan_agent") -> logging.Logger:
    """Return a configured logger. Multiple calls with the same name return the same instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)

    level = logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Rotating file
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger
