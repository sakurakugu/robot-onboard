from __future__ import annotations

import json
import urllib.request
from typing import Any

from sparkrobot_common import ROBOT_SERVER_URL


class 机器狗遥测错误(RuntimeError):
    """机器狗遥测访问错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class 机器狗遥测服务:
    """访问 robot-server 完整遥测接口。"""

    def __init__(self, telemetry_url: str | None = None, timeout_sec: float = 1.0) -> None:
        self.telemetry_url = telemetry_url or f"{ROBOT_SERVER_URL}/api/v1/telemetry/full"
        self.timeout_sec = timeout_sec

    def 获取完整遥测(self) -> dict[str, Any]:
        """获取完整遥测快照。"""
        request = urllib.request.Request(
            self.telemetry_url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise 机器狗遥测错误("robot_telemetry_unavailable", f"访问机器狗遥测失败: {exc}") from exc

        try:
            message = json.loads(body)
        except json.JSONDecodeError as exc:
            raise 机器狗遥测错误("robot_telemetry_invalid_json", f"机器狗遥测响应不是合法 JSON: {exc}") from exc

        if not isinstance(message, dict):
            raise 机器狗遥测错误("robot_telemetry_invalid_response", "机器狗遥测响应格式无效")
        if not bool(message.get("success", False)):
            raise 机器狗遥测错误("robot_telemetry_failed", f"机器狗遥测接口返回失败: {message}")

        data = message.get("data", {})
        if not isinstance(data, dict):
            raise 机器狗遥测错误("robot_telemetry_invalid_data", "机器狗遥测 data 字段格式无效")
        return data


__all__ = ["机器狗遥测服务", "机器狗遥测错误"]
