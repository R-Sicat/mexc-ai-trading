import logging
import sys
from pathlib import Path
from datetime import datetime

import structlog

LOG_DIR = Path(__file__).parent.parent.parent / "data" / "logs"


def setup_logging(level: str = "INFO") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"sniper_{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    root_logger.addHandler(console)

    # File handler (JSON lines)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.FileHandler(LOG_DIR / "errors.log")
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
