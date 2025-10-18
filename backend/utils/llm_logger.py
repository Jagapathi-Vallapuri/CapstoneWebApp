import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

_LOGGER_NAME = "llm_file_logger"
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
_LOG_FILE = os.path.join(_LOG_DIR, 'llm.log')


def _ensure_logger() -> logging.Logger:
    os.makedirs(_LOG_DIR, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.FileHandler(_LOG_FILE, encoding='utf-8')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # Do not propagate to root to avoid terminal output
        logger.propagate = False
    return logger


def log_llm_event(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Write a single JSON line with timestamp, event type, and payload.

    event: short label, e.g., 'chat.response', 'extraction.gemini.raw', 'error'
    payload: arbitrary JSON-serializable dict
    """
    try:
        logger = _ensure_logger()
        line = {
            "ts": datetime.utcnow().isoformat() + 'Z',
            "event": event,
            "payload": payload or {},
        }
        logger.info(json.dumps(line, ensure_ascii=False))
    except Exception:
        pass
