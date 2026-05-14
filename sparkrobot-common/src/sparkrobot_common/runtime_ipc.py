"""
运行时 IPC 协议与客户端
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from sparkrobot_common.const import ORG_NAME
from sparkrobot_common.logger import get_logger
from sparkrobot_common.utils import 生成UUID, 获取IPC路径

logger = get_logger("runtime-ipc")

运行时默认项目名 = "robot-runtime"
运行时状态事件名 = "state"
运行时默认超时秒数 = 20.0


class 运行时IPC错误(RuntimeError):
    """运行时 IPC 调用错误。"""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def 格式化运行时IPC异常(exc: Exception) -> dict[str, Any]:
    """把运行时 IPC 异常转换为统一错误结构。"""
    if isinstance(exc, 运行时IPC错误):
        return {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }

    if isinstance(exc, FileNotFoundError):
        return {
            "code": "runtime_socket_not_found",
            "message": "未找到 robot-runtime 的 IPC Socket",
            "details": {},
        }

    if isinstance(exc, ConnectionRefusedError):
        return {
            "code": "runtime_connection_refused",
            "message": "robot-runtime IPC 连接被拒绝",
            "details": {},
        }

    if isinstance(exc, TimeoutError):
        return {
            "code": "runtime_timeout",
            "message": "访问 robot-runtime 超时",
            "details": {},
        }

    if isinstance(exc, OSError):
        return {
            "code": "runtime_os_error",
            "message": f"访问 robot-runtime 失败: {exc}",
            "details": {},
        }

    return {
        "code": "runtime_unknown_error",
        "message": str(exc),
        "details": {},
    }


def 获取运行时IPC路径(project_name: str = 运行时默认项目名) -> Path:
    """获取运行时 IPC Socket 路径。"""
    return 获取IPC路径(ORG_NAME, project_name)


def 构建运行时请求(method: str, params: dict[str, Any] | None = None, request_id: str | None = None) -> dict[str, Any]:
    """构建运行时请求消息。"""
    return {
        "type": "request",
        "id": request_id or 生成UUID(),
        "method": method,
        "params": params or {},
    }


def 构建运行时成功响应(request_id: str, result: Any) -> dict[str, Any]:
    """构建成功响应消息。"""
    return {
        "type": "response",
        "id": request_id,
        "success": True,
        "result": result,
    }


def 构建运行时错误响应(
    request_id: str,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建错误响应消息。"""
    return {
        "type": "response",
        "id": request_id,
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        },
    }


def 构建运行时事件(event: str, data: Any) -> dict[str, Any]:
    """构建事件消息。"""
    return {
        "type": "event",
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def 编码运行时消息(message: dict[str, Any]) -> bytes:
    """编码为 JSON Line。"""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def 解码运行时消息(raw: bytes) -> dict[str, Any]:
    """从 JSON Line 解码消息。"""
    payload = json.loads(raw.decode("utf-8").strip())
    if not isinstance(payload, dict):
        raise ValueError("IPC 消息必须是 JSON 对象")
    return payload


class 运行时IPC客户端:
    """运行时 IPC 客户端。"""

    def __init__(self, project_name: str = 运行时默认项目名, timeout_sec: float = 运行时默认超时秒数) -> None:
        self.project_name = project_name
        self.timeout_sec = timeout_sec

    @property
    def socket_path(self) -> Path:
        """返回 Socket 路径。"""
        return 获取运行时IPC路径(self.project_name)

    async def 调用(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float | None = None) -> dict[str, Any]:
        """执行一次请求响应式 RPC 调用。"""
        request = 构建运行时请求(method, params)
        effective_timeout = timeout_sec or self.timeout_sec
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(self.socket_path)),  # type: ignore[attr-defined]
            timeout=effective_timeout,
        )
        try:
            writer.write(编码运行时消息(request))
            await writer.drain()

            raw = await asyncio.wait_for(reader.readline(), timeout=effective_timeout)
            if not raw:
                raise RuntimeError("运行时 IPC 连接已关闭")

            response = 解码运行时消息(raw)
            return self._解析响应(response, request["id"])
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def 订阅状态(self, mode: str = "summary", interval_sec: float = 1.0) -> AsyncIterator[dict[str, Any]]:
        """订阅状态事件流。"""
        request = 构建运行时请求(
            "runtime.subscribe_state",
            {
                "mode": mode,
                "interval_sec": interval_sec,
            },
        )
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path))  # type: ignore[attr-defined]
        try:
            writer.write(编码运行时消息(request))
            await writer.drain()

            raw = await reader.readline()
            if not raw:
                raise RuntimeError("运行时 IPC 连接已关闭")

            response = 解码运行时消息(raw)
            self._解析响应(response, request["id"])

            while True:
                raw = await reader.readline()
                if not raw:
                    break
                message = 解码运行时消息(raw)
                if message.get("type") != "event" or message.get("event") != 运行时状态事件名:
                    continue
                data = message.get("data", {})
                if isinstance(data, dict):
                    yield data
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def 探活(self) -> dict[str, Any]:
        """检查运行时是否在线。"""
        return await self.调用("runtime.ping")

    async def 获取摘要(self) -> dict[str, Any]:
        """获取运行时状态摘要。"""
        return await self.调用("runtime.get_summary")

    async def 获取完整状态(self) -> dict[str, Any]:
        """获取完整运行时状态。"""
        return await self.调用("runtime.get_state")

    async def 获取地图预览(self) -> dict[str, Any]:
        """获取最近一帧建图地图预览。"""
        return await self.调用("mapping.get_preview")

    async def 开始手动控制(
        self,
        mode: str = "move",
        source: str = "runtime",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """开始手动控制会话。"""
        params: dict[str, Any] = {
            "mode": mode,
            "source": source,
        }
        if session_id:
            params["session_id"] = session_id
        return await self.调用("manual.start_session", params)

    async def 更新手动速度(
        self,
        mode: str,
        vx: float,
        vy: float = 0.0,
        wz: float = 0.0,
        source: str = "runtime",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """更新手动控制速度。"""
        params: dict[str, Any] = {
            "mode": mode,
            "vx": vx,
            "vy": vy,
            "wz": wz,
            "source": source,
        }
        if session_id:
            params["session_id"] = session_id
        return await self.调用("manual.update_velocity", params)

    async def 停止手动控制(self, session_id: str | None = None) -> dict[str, Any]:
        """停止手动控制会话。"""
        params = {"session_id": session_id} if session_id else {}
        return await self.调用("manual.stop", params)

    async def 执行直连控制(self, payload: dict[str, Any], source: str = "runtime") -> dict[str, Any]:
        """执行手机直连专用控制命令，保留旧版 SDK 控制语义。"""
        return await self.调用(
            "direct_control.execute",
            {
                "payload": payload,
                "source": source,
            },
        )

    async def 立即急停(self, source: str = "runtime") -> dict[str, Any]:
        """立即触发机器狗急停，不经过普通动作排队。"""
        return await self.调用(
            "manual.estop",
            {
                "source": source,
            },
        )

    async def 执行动作(
        self,
        action_name: str,
        parameters: dict[str, Any] | None = None,
        source: str = "runtime",
        action_id: str | None = None,
    ) -> dict[str, Any]:
        """执行动作请求。"""
        params: dict[str, Any] = {
            "action_name": action_name,
            "parameters": parameters or {},
            "source": source,
        }
        if action_id:
            params["action_id"] = action_id
        return await self.调用("action.execute", params)

    async def 取消动作(self, action_id: str | None = None) -> dict[str, Any]:
        """取消动作请求。"""
        params = {"action_id": action_id} if action_id else {}
        return await self.调用("action.cancel", params)

    async def 开始建图(self, map_name: str | None = None) -> dict[str, Any]:
        """开始建图。"""
        params = {"map_name": map_name} if map_name else {}
        return await self.调用("mapping.start", params)

    async def 停止建图(self, save_map: bool | None = None) -> dict[str, Any]:
        """停止建图。"""
        params = {"save_map": save_map} if save_map is not None else {}
        return await self.调用("mapping.stop", params)

    async def 加载地图(self, map_name: str) -> dict[str, Any]:
        """加载地图。"""
        return await self.调用("mapping.load", {"map_name": map_name})

    async def 开始定位(self, map_name: str | None = None) -> dict[str, Any]:
        """开始定位。"""
        params = {"map_name": map_name} if map_name else {}
        return await self.调用("localization.start", params)

    async def 停止定位(self) -> dict[str, Any]:
        """停止定位。"""
        return await self.调用("localization.stop")

    async def 设置初始位姿(
        self,
        x: float,
        y: float,
        yaw: float,
        frame_id: str = "map",
        map_name: str | None = None,
    ) -> dict[str, Any]:
        """发布定位初始位姿。"""
        params: dict[str, Any] = {
            "x": x,
            "y": y,
            "yaw": yaw,
            "frame_id": frame_id,
        }
        if map_name:
            params["map_name"] = map_name
        return await self.调用("localization.set_initial_pose", params)

    async def 导航到目标(
        self,
        x: float,
        y: float,
        yaw: float,
        frame_id: str = "map",
        map_name: str | None = None,
        goal_id: str | None = None,
    ) -> dict[str, Any]:
        """创建导航任务。"""
        params: dict[str, Any] = {
            "x": x,
            "y": y,
            "yaw": yaw,
            "frame_id": frame_id,
        }
        if map_name:
            params["map_name"] = map_name
        if goal_id:
            params["goal_id"] = goal_id
        return await self.调用("navigation.navigate_to", params)

    async def 取消导航(self) -> dict[str, Any]:
        """取消导航。"""
        return await self.调用("navigation.cancel")

    async def 开始巡逻(self, task_name: str, waypoint_file: str) -> dict[str, Any]:
        """创建巡逻任务。"""
        return await self.调用(
            "patrol.start",
            {
                "task_name": task_name,
                "waypoint_file": waypoint_file,
            },
        )

    async def 暂停任务(self) -> dict[str, Any]:
        """暂停当前任务。"""
        return await self.调用("task.pause")

    async def 恢复任务(self) -> dict[str, Any]:
        """恢复当前任务。"""
        return await self.调用("task.resume")

    async def 终止任务(self) -> dict[str, Any]:
        """终止当前任务。"""
        return await self.调用("task.terminate")

    def _解析响应(self, response: dict[str, Any], request_id: str) -> dict[str, Any]:
        """解析响应消息。"""
        if response.get("type") != "response":
            raise RuntimeError("运行时 IPC 响应类型无效")

        response_id = str(response.get("id", ""))
        if response_id != request_id:
            raise RuntimeError("运行时 IPC 响应 ID 不匹配")

        if not bool(response.get("success", False)):
            error = response.get("error", {})
            code = str(error.get("code", "runtime_ipc_error"))
            message = str(error.get("message", "运行时 IPC 调用失败"))
            details = error.get("details", {})
            if not isinstance(details, dict):
                details = {"raw": details}
            raise 运行时IPC错误(code, message, details)

        result = response.get("result", {})
        if isinstance(result, dict):
            return result
        return {"value": result}


__all__ = [
    "运行时IPC客户端",
    "运行时IPC错误",
    "格式化运行时IPC异常",
    "运行时默认项目名",
    "运行时状态事件名",
    "运行时默认超时秒数",
    "获取运行时IPC路径",
    "构建运行时请求",
    "构建运行时成功响应",
    "构建运行时错误响应",
    "构建运行时事件",
    "编码运行时消息",
    "解码运行时消息",
]
