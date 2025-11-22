# common/logger.py
from loguru import logger
import sys

def init_logger() -> None:
    """Initialize Loguru logger with sane defaults."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", enqueue=True, backtrace=False, diagnose=False)
