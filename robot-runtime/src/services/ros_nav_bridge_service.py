from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

默认导航桥Socket路径 = Path("/tmp/sparkrobot/ros-nav-bridge.sock")


class ROS导航桥错误(RuntimeError):
    """ROS 导航桥访问错误。"""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ROS导航桥客户端:
    """负责访问本地 ROS2 导航桥 Socket。"""

    def __init__(self, socket_path: Path | None = None, timeout_sec: float = 5.0) -> None:
        self.socket_path = socket_path or 默认导航桥Socket路径
        self.timeout_sec = timeout_sec

    async def 等待就绪(self, timeout_sec: float = 10.0, interval_sec: float = 0.5) -> dict[str, Any]:
        """等待桥接节点上线。"""
        deadline = asyncio.get_running_loop().time() + timeout_sec

        while True:
            try:
                return await self.探活(timeout_sec=min(self.timeout_sec, interval_sec))
            except Exception as exc:
                if asyncio.get_running_loop().time() >= deadline:
                    raise self._转换异常(exc) from exc
                await asyncio.sleep(interval_sec)

    async def 探活(self, timeout_sec: float | None = None) -> dict[str, Any]:
        """检查导航桥是否在线。"""
        return await self._调用("bridge.ping", {}, timeout_sec=timeout_sec)

    async def 导航到目标(self, goal: dict[str, Any], timeout_sec: float | None = None) -> dict[str, Any]:
        """发送导航目标。"""
        return await self._调用("navigation.navigate_to", goal, timeout_sec=timeout_sec)

    async def 取消导航(self, timeout_sec: float | None = None) -> dict[str, Any]:
        """取消当前导航目标。"""
        return await self._调用("navigation.cancel", {}, timeout_sec=timeout_sec)

    async def 获取导航状态(self, timeout_sec: float | None = None) -> dict[str, Any]:
        """获取桥接节点当前导航状态。"""
        return await self._调用("navigation.get_status", {}, timeout_sec=timeout_sec)

    async def 获取激光扫描(self, timeout_sec: float | None = None) -> dict[str, Any]:
        """获取最近一帧激光扫描。"""
        return await self._调用("lidar.get_scan", {}, timeout_sec=timeout_sec)

    async def _调用(self, method: str, params: dict[str, Any], timeout_sec: float | None = None) -> dict[str, Any]:
        """执行一次请求响应式调用。"""
        self._校验平台()
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
            payload = (json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            writer.write(payload)
            await writer.drain()

            raw = await asyncio.wait_for(reader.readline(), timeout=effective_timeout)
            if not raw:
                raise ROS导航桥错误("ros_nav_bridge_closed", "导航桥连接已关闭")

            response = json.loads(raw.decode("utf-8").strip())
            if not isinstance(response, dict):
                raise ROS导航桥错误("ros_nav_bridge_invalid_response", "导航桥响应格式无效")
            if response.get("type") != "response":
                raise ROS导航桥错误("ros_nav_bridge_invalid_type", "导航桥响应类型无效")
            if str(response.get("id", "")) != request["id"]:
                raise ROS导航桥错误("ros_nav_bridge_invalid_id", "导航桥响应 ID 不匹配")

            if not bool(response.get("success", False)):
                error = response.get("error", {})
                if not isinstance(error, dict):
                    error = {"message": str(error)}
                details = error.get("details", {})
                if not isinstance(details, dict):
                    details = {"raw": details}
                raise ROS导航桥错误(
                    str(error.get("code", "ros_nav_bridge_error")),
                    str(error.get("message", "导航桥调用失败")),
                    details,
                )

            result = response.get("result", {})
            if isinstance(result, dict):
                return result
            return {"value": result}
        except ROS导航桥错误:
            raise
        except Exception as exc:
            raise self._转换异常(exc) from exc
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _校验平台(self) -> None:
        if os.name != "posix":
            raise ROS导航桥错误("ros_platform_unsupported", "ROS 导航桥当前只支持 Linux/WSL。")

    def _转换异常(self, exc: Exception) -> ROS导航桥错误:
        if isinstance(exc, ROS导航桥错误):
            return exc
        if isinstance(exc, FileNotFoundError):
            return ROS导航桥错误("ros_nav_bridge_not_found", "未找到 ROS 导航桥 Socket。")
        if isinstance(exc, ConnectionRefusedError):
            return ROS导航桥错误("ros_nav_bridge_refused", "ROS 导航桥连接被拒绝。")
        if isinstance(exc, TimeoutError):
            return ROS导航桥错误("ros_nav_bridge_timeout", "访问 ROS 导航桥超时。")
        if isinstance(exc, OSError):
            return ROS导航桥错误("ros_nav_bridge_os_error", f"访问 ROS 导航桥失败: {exc}")
        return ROS导航桥错误("ros_nav_bridge_unknown", str(exc))


__all__ = [
    "ROS导航桥客户端",
    "ROS导航桥错误",
    "默认导航桥Socket路径",
]
