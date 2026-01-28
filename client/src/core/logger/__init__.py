import io
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

from core.config import APP_NAME

LEVEL_NAME_CN = {
    "DEBUG": "调试",
    "INFO": "信息",
    "WARNING": "警告",
    "ERROR": "错误",
    "CRITICAL": "严重",
}

class CNLevelFormatter(logging.Formatter):
    def __init__(self, fmt: str, time_mode: str, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.time_mode = time_mode

    def formatTime(self, record, datefmt=None):
        if self.time_mode == "console":
            local_dt = datetime.fromtimestamp(record.created).astimezone()
            return local_dt.strftime(datefmt or "%H:%M:%S.%f")
        local_dt = datetime.fromtimestamp(record.created).astimezone()
        ts = local_dt.isoformat(timespec="microseconds")
        if ts.endswith("Z") or ts.endswith("z"):
            ts = ts[:-1] + "+00:00"
        return ts

    def format(self, record):
        original = record.levelname
        record.levelname = LEVEL_NAME_CN.get(original, original)
        try:
            return super().format(record)
        finally:
            record.levelname = original


logger = logging.getLogger(APP_NAME)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


def _resolve_console_stream() -> Optional[io.TextIOBase]:
    """ 解析控制台输出流，优先选择stdout，其次选择stderr """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOBase) and stream.isatty():
            return stream
    return None


def _build_log_path(base_dir: Path, date_value: Optional[datetime] = None) -> Path:
    """ 构建日志文件路径，按日期分类 """
    now = date_value or datetime.now().astimezone()
    date_folder = now.date().isoformat()
    date_compact = now.strftime("%Y%m%d")
    daily_dir = base_dir / date_folder
    daily_dir.mkdir(parents=True, exist_ok=True)
    return daily_dir / f"{APP_NAME}_{date_compact}.log"


def configure_logger(
    log_dir: Union[str, Path],
    level: Union[int, str] = logging.INFO,
    max_file_size_mb: Optional[int] = None,
) -> logging.Logger:
    resolved_level = level
    if isinstance(resolved_level, str):
        resolved_level = getattr(logging, resolved_level.upper(), logging.INFO)
    base_dir = Path(log_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    log_path = _build_log_path(base_dir)

    file_formatter = CNLevelFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d %(funcName)s] %(message)s",
        time_mode="file",
    )
    file_handler: logging.Handler
    if max_file_size_mb:
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_file_size_mb * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    else:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(file_formatter)

    handlers: list[logging.Handler] = [file_handler]
    console_stream = _resolve_console_stream()
    if console_stream is not None:
        console_handler = logging.StreamHandler(console_stream)
        console_formatter = CNLevelFormatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d %(funcName)s] %(message)s",
            time_mode="console",
            datefmt="%H:%M:%S.%f",
        )
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)

    logger.setLevel(resolved_level)
    logger.handlers = []
    for handler in handlers:
        logger.addHandler(handler)
    logger.propagate = False
    return logger

__all__ = ["logger", "configure_logger", "CNLevelFormatter"]
