import logging
from datetime import datetime, timedelta, timezone

LEVEL_NAME_CN = {
    "DEBUG": "调试",
    "INFO": "信息",
    "WARNING": "警告",
    "ERROR": "错误",
    "CRITICAL": "严重",
}

tz = timezone(timedelta(hours=8))


class CNLevelFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        if datefmt:
            return datetime.fromtimestamp(record.created, tz=tz).strftime(datefmt)
        return datetime.fromtimestamp(record.created, tz=tz).isoformat(timespec="microseconds")

    def format(self, record):
        original = record.levelname
        record.levelname = LEVEL_NAME_CN.get(original, original)
        try:
            return super().format(record)
        finally:
            record.levelname = original


logger = logging.getLogger("robot_control")
if not logger.handlers:
    handler = logging.StreamHandler()
    console_formatter = CNLevelFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S.%f")
    handler.setFormatter(console_formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

__all__ = ["logger"]
