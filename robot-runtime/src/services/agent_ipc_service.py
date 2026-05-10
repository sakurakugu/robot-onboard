from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from sparkrobot_common import ORG_NAME, 获取IPC路径

默认机器人代理Socket路径 = 获取IPC路径(ORG_NAME, "robot-agent")


class 机器人代理IPC错误(RuntimeError):
    """本地 robot-agent IPC 调用错误。"""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class 机器人代理IPC客户端:
    """访问本地 robot-agent IPC 的轻量客户端。"""

    def __init__(self, socket_path: Path | None = None, timeout_sec: float = 5.0) -> None:
        self.socket_path = socket_path or 默认机器人代理Socket路径
        self.timeout_sec = timeout_sec

    async def 执行动作(
        self,
        action_name: str,
        parameters: dict[str, Any] | None = None,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        return await self._调用(
            "action.execute",
            {
                "action_name": action_name,
                "parameters": parameters or {},
            },
            timeout_sec=timeout_sec,
        )

    async def 取消动作(self, timeout_sec: float | None = None) -> dict[str, Any]:
        return await self._调用("action.cancel", {}, timeout_sec=timeout_sec)

    async def _调用(self, method: str, params: dict[str, Any], timeout_sec: float | None = None) -> dict[str, Any]:
        effective_timeout = timeout_sec or self.timeout_sec
        request = {
            "type": "request",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),  # type: ignore[attr-defined]
                timeout=effective_timeout,
            )
        except Exception as exc:
            raise self._转换异常(exc) from exc

        try:
            writer.write((json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            await writer.drain()

            raw = await asyncio.wait_for(reader.readline(), timeout=effective_timeout)
            if not raw:
                raise 机器人代理IPC错误("robot_agent_ipc_closed", "robot-agent IPC 连接已关闭")

            response = json.loads(raw.decode("utf-8").strip())
            if not isinstance(response, dict):
                raise 机器人代理IPC错误("robot_agent_ipc_invalid_response", "robot-agent IPC 响应格式无效")
            if response.get("type") != "response":
                raise 机器人代理IPC错误("robot_agent_ipc_invalid_type", "robot-agent IPC 响应类型无效")
            if str(response.get("id", "")) != request["id"]:
                raise 机器人代理IPC错误("robot_agent_ipc_invalid_id", "robot-agent IPC 响应 ID 不匹配")

            if not bool(response.get("success", False)):
                error = response.get("error", {})
                if not isinstance(error, dict):
                    error = {"message": str(error)}
                details = error.get("details", {})
                if not isinstance(details, dict):
                    details = {"raw": details}
                raise 机器人代理IPC错误(
                    str(error.get("code", "robot_agent_ipc_error")),
                    str(error.get("message", "robot-agent IPC 调用失败")),
                    details,
                )

            result = response.get("result", {})
            if isinstance(result, dict):
                return result
            return {"value": result}
        except 机器人代理IPC错误:
            raise
        except Exception as exc:
            raise self._转换异常(exc) from exc
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _转换异常(self, exc: Exception) -> 机器人代理IPC错误:
        if isinstance(exc, 机器人代理IPC错误):
            return exc
        if isinstance(exc, FileNotFoundError):
            return 机器人代理IPC错误("robot_agent_ipc_not_found", "未找到 robot-agent IPC Socket。")
        if isinstance(exc, ConnectionRefusedError):
            return 机器人代理IPC错误("robot_agent_ipc_refused", "robot-agent IPC 连接被拒绝。")
        if isinstance(exc, TimeoutError):
            return 机器人代理IPC错误("robot_agent_ipc_timeout", "访问 robot-agent IPC 超时。")
        if isinstance(exc, OSError):
            return 机器人代理IPC错误("robot_agent_ipc_os_error", f"访问 robot-agent IPC 失败: {exc}")
        return 机器人代理IPC错误("robot_agent_ipc_unknown", str(exc))


__all__ = [
    "机器人代理IPC客户端",
    "机器人代理IPC错误",
    "默认机器人代理Socket路径",
]
