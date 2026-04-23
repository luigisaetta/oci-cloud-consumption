"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Shared utility helpers exposed by the utils package.
"""

import json
import logging
from typing import Any


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


def emit_structured_log(
    logger: logging.Logger,
    *,
    component: str,
    operation: str,
    status: str,
    error_details: str = "",
    **extra: Any,
) -> None:
    """Emit a normalized JSON log line with observability-required fields."""
    payload = {
        "component": component,
        "operation": operation,
        "status": status,
        "error_details": error_details,
    }
    payload.update(extra)
    logger.info("%s", json.dumps(payload, default=str, sort_keys=True))
