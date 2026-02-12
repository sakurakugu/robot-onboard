from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sparkrobot_common import WORKSPACE_DIR

LOG_FILE_PATTERN = re.compile(r".+\.log(?:\.\d+)?$")
LOG_LINE_TS_PATTERN = re.compile(r"^\[(?P<timestamp>[^\]]+)\]")


@dataclass(frozen=True)
class 日志文件:
    路径: Path
    相对路径: str
    应用名: str
    日期目录: str
    文件名: str
    大小字节: int
    修改时间: str


class 日志服务:
    def __init__(self, 日志根目录: Path | None = None) -> None:
        self.日志根目录 = 日志根目录 or (WORKSPACE_DIR / "logs")

    def 获取日志列表(self, app_name: str | None = None) -> tuple[list[dict[str, Any]], list[str], list[日志文件]]:
        if not self.日志根目录.exists():
            return [], [], []

        文件列表: list[日志文件] = []
        应用名集合: set[str] = set()

        for file_path in self.日志根目录.rglob("*"):
            if not file_path.is_file() or not LOG_FILE_PATTERN.fullmatch(file_path.name):
                continue

            relative_path = file_path.relative_to(self.日志根目录)
            normalized_relative_path = relative_path.as_posix()
            parts = relative_path.parts
            detected_app_name = parts[0] if len(parts) >= 1 else "unknown"
            应用名集合.add(detected_app_name)

            if app_name and detected_app_name != app_name:
                continue

            date_folder = parts[1] if len(parts) >= 2 else ""
            stat = file_path.stat()
            modified_time = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()

            文件列表.append(
                日志文件(
                    路径=file_path,
                    相对路径=normalized_relative_path,
                    应用名=detected_app_name,
                    日期目录=date_folder,
                    文件名=file_path.name,
                    大小字节=stat.st_size,
                    修改时间=modified_time,
                )
            )

        文件列表.sort(key=lambda item: item.修改时间, reverse=True)
        响应列表 = [
            {
                "relative_path": item.相对路径,
                "app_name": item.应用名,
                "date_folder": item.日期目录,
                "file_name": item.文件名,
                "size_bytes": item.大小字节,
                "modified_time": item.修改时间,
            }
            for item in 文件列表
        ]
        return 响应列表, sorted(应用名集合), 文件列表

    def 打包下载(
        self,
        start_time: datetime,
        end_time: datetime,
        app_name: str | None = None,
    ) -> tuple[bytes, str]:
        start = self._标准化时间(start_time)
        end = self._标准化时间(end_time)

        if start > end:
            raise ValueError("开始时间不能晚于结束时间")

        _, _, files = self.获取日志列表(app_name=app_name)
        if not files:
            raise FileNotFoundError("未找到可用日志文件")

        output = io.BytesIO()
        matched_files = 0

        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file_item in files:
                matched_content = self._筛选日志内容(file_item.路径, start, end)
                if not matched_content:
                    continue
                matched_files += 1
                zip_file.writestr(file_item.相对路径, matched_content)

            if matched_files == 0:
                raise FileNotFoundError("指定时间段内没有匹配的日志")

        filename = self._生成压缩包文件名(start, end, app_name)
        return output.getvalue(), filename

    def _筛选日志内容(self, file_path: Path, start: datetime, end: datetime) -> str:
        lines: list[str] = []
        include_current_block = False

        with file_path.open("r", encoding="utf-8", errors="ignore") as log_file:
            for line in log_file:
                timestamp = self._解析日志时间(line)
                if timestamp is not None:
                    include_current_block = start <= timestamp <= end
                if include_current_block:
                    lines.append(line)

        return "".join(lines)

    def _解析日志时间(self, line: str) -> datetime | None:
        match = LOG_LINE_TS_PATTERN.match(line)
        if not match:
            return None
        raw_timestamp = match.group("timestamp")
        try:
            parsed = datetime.fromisoformat(raw_timestamp)
        except ValueError:
            return None
        return self._标准化时间(parsed)

    def _标准化时间(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.astimezone()
        return value.astimezone()

    def _生成压缩包文件名(self, start: datetime, end: datetime, app_name: str | None) -> str:
        app = app_name or "all"
        start_text = start.strftime("%Y%m%d_%H%M%S")
        end_text = end.strftime("%Y%m%d_%H%M%S")
        return f"logs_{app}_{start_text}_{end_text}.zip"


_log_service_singleton: 日志服务 | None = None


def 获取日志服务单例() -> 日志服务:
    global _log_service_singleton
    if _log_service_singleton is None:
        _log_service_singleton = 日志服务()
    return _log_service_singleton
