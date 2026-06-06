from __future__ import annotations

import logging

from monitor_control_app.core.config_store import get_log_path


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("monitor_control_app")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_path = get_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logger.addHandler(file_handler)
    logger.info("Monitor Control started")
    return logger
