"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Shared utility helpers exposed by the utils package.
"""

import logging


def get_console_logger(name: str = "ConsoleLogger", level: str = "INFO"):
    """Return a console logger configured to avoid duplicated handlers."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger
