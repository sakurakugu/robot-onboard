import asyncio
from typing import Any, Awaitable, Callable

from sparkrobot_common import get_logger

from src.modules.runtime.runtime_client import 本地运行时客户端
from src.modules.vision import capture_photo

logger = get_logger("robot-agent")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class 直连控制处理器:
    """负责处理手机直连 WebSocket 的控制指令。"""

    def __init__(
        self,
        audio_capture: Any,
        sdk_mode_manager: Any,
        runtime_client: 本地运行时客户端,
    ) -> None:
        self.audio_capture = audio_capture
        self.sdk_mode_manager = sdk_mode_manager
        self.runtime_client = runtime_client

    def 处理控制指令(self, data: dict[str, Any]) -> None:
        """处理来自手机直连 WebSocket 的同步控制指令。"""
        command = data.get("command", "")
        if command in ("joystick", "joystick_stop", "estop", "update_velocity", "stop", "emergency_stop"):
            asyncio.create_task(self._优先转发控制命令(data))
        elif command == "action":
            asyncio.create_task(self._优先转发动作命令(data))
        elif command == "mic_control":
            enabled = bool(data.get("enabled", True))
            self.audio_capture.audio_streaming_enabled = enabled
            logger.info(f"[直连控制] 麦克风采集{'开启' if enabled else '关闭'}")
        elif command == "switch_control_mode":
            mode = data.get("mode", "move")
            logger.info(f"[直连控制] 控制模式切换为: {mode}")
        else:
            logger.debug(f"[直连控制] 未知指令类型: {command}")

    async def 处理异步命令(self, data: dict[str, Any], send_fn: SendFn) -> None:
        """处理来自手机直连 WebSocket 的异步指令。"""
        command = data.get("command", "")
        request_id = data.get("requestId", "direct")

        if command == "camera_capture":
            logger.info(f"[直连控制] 收到拍照请求: {request_id}")
            try:
                loop = asyncio.get_event_loop()
                rtsp_url = "rtsp://127.0.0.1:8554/test"
                image_base64 = await loop.run_in_executor(None, capture_photo, rtsp_url, 5)
                await send_fn({
                    "type": "camera_capture_response",
                    "data": {
                        "requestId": request_id,
                        "success": bool(image_base64),
                        "image": image_base64,
                        "format": "jpeg",
                    },
                })
                logger.info(f"[直连控制] 拍照完成: {request_id}, 有图={'是' if image_base64 else '否'}")
            except Exception as e:
                logger.error(f"[直连控制] 拍照失败: {e}", exc_info=True)
                await send_fn({
                    "type": "camera_capture_response",
                    "data": {
                        "requestId": request_id,
                        "success": False,
                        "error": str(e),
                    },
                })
            return

        if command == "sdk_mode":
            enabled = data.get("enabled")
            logger.info(f"[直连控制] SDK 模式切换请求: {enabled}")
            if enabled is None:
                await send_fn({
                    "type": "sdk_mode_response",
                    "data": {"requestId": request_id, "success": False, "error": "enabled 参数不能为空"},
                })
                return

            success, sdk_mode, error = await self.sdk_mode_manager.切换(bool(enabled), "[直连控制]")
            payload: dict[str, Any] = {
                "requestId": request_id,
                "success": success,
            }
            if success:
                payload["sdkMode"] = sdk_mode
                logger.info(f"[直连控制] SDK 模式已切换为: {'SDK' if sdk_mode else '遥控'}")
            else:
                payload["error"] = error or "SDK 模式切换失败"
                logger.error(f"[直连控制] SDK 模式切换失败: {payload['error']}")
            await send_fn({"type": "sdk_mode_response", "data": payload})
            return

        logger.debug(f"[直连控制] 未知异步指令: {command}")

    async def _优先转发控制命令(self, data: dict[str, Any]) -> None:
        await self.runtime_client.执行直连控制命令(data, source="direct-control")

    async def _优先转发动作命令(self, data: dict[str, Any]) -> None:
        await self.runtime_client.执行动作命令(data, source="direct-control")
