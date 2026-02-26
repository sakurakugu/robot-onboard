"""本地 WebSocket 直连控制服务器

手机与机器狗处于同一局域网时，可直接连接此服务，绕过云端服务器，
显著降低控制延迟。

端口: 8082
连接地址: ws://<机器狗IP>:8082

支持的消息格式（两种均可）：
  格式1（服务器风格）:
    {"type": "control_command", "data": {"command": "joystick", ...}}

  格式2（直接格式）:
    {"command": "joystick", "mode": "move", "x": 0.5, "y": 0.0, "speed": 5}

command 取值:
  - "joystick"          摇杆移动
  - "joystick_stop"     摇杆停止
  - "estop"             急停
  - "action"            执行动作，需附加 "action" 字段（如 "stand_up"）
  - "mic_control"       麦克风开关，需附加 "enabled" 字段
  - "sdk_mode"          切换 SDK/遥控模式，需附加 "enabled" 字段
  - "switch_control_mode" 切换移动/姿态模式，需附加 "mode" 字段
  - "camera_capture"    拍照（异步，机器人通过 WebSocket 回传 base64 图像）
"""

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")

DIRECT_CONTROL_PORT = 8082

# 异步发送函数类型：接收一条 dict，序列化后发给客户端
SendFn = Callable[[Dict[str, Any]], Awaitable[None]]

# 需要异步响应的 command 集合（如拍照、SDK 模式切换等耗时操作）
_ASYNC_COMMANDS = {"camera_capture", "sdk_mode"}


class WsControlServer:
    """本地 WebSocket 控制服务器，供手机在局域网内直连"""

    def __init__(
        self,
        on_command: Callable[[Dict[str, Any]], None],
        on_async_command: Optional[Callable[[Dict[str, Any], SendFn], Awaitable[None]]] = None,
    ) -> None:
        """
        Args:
            on_command:       收到同步控制指令时的回调（摇杆、急停、麦克风等低延迟指令）
            on_async_command: 收到需要异步响应的指令时的回调（拍照等），
                              签名：async (data, send_fn) -> None
        """
        self._on_command = on_command
        self._on_async_command = on_async_command
        self._server = None
        self._connected: Set = set()

    async def 广播(self, message: Dict[str, Any]) -> None:
        """向所有已连接客户端广播消息"""
        if not self._connected:
            return
        raw = json.dumps(message, ensure_ascii=False)
        for ws in list(self._connected):
            try:
                await ws.send(raw)
            except Exception:
                pass

    async def _处理连接(self, websocket) -> None:
        addr = getattr(websocket, "remote_address", "unknown")
        logger.info(f"[直连控制] 手机已接入: {addr}")
        self._connected.add(websocket)
        try:
            async for raw in websocket:
                try:
                    msg: Dict[str, Any] = json.loads(raw)
                except Exception:
                    continue

                # 解析消息格式
                if msg.get("type") == "control_command":
                    # 格式1：{"type": "control_command", "data": {...}}
                    data = msg.get("data", {})
                elif "command" in msg:
                    # 格式2：{"command": "...", ...}
                    data = msg
                else:
                    data = msg

                command = data.get("command", "")

                # 需要异步响应的指令（如拍照）
                if command in _ASYNC_COMMANDS and self._on_async_command:
                    async def _send_fn(resp: Dict[str, Any], _ws=websocket) -> None:
                        try:
                            await _ws.send(json.dumps(resp, ensure_ascii=False))
                        except Exception as exc:
                            logger.warning(f"[直连控制] 发送响应失败: {exc}")

                    asyncio.ensure_future(self._on_async_command(data, _send_fn))
                else:
                    try:
                        self._on_command(data)
                    except Exception as e:
                        logger.warning(f"[直连控制] 处理指令失败: {e}")

        except Exception as e:
            logger.debug(f"[直连控制] 连接异常: {e}")
        finally:
            self._connected.discard(websocket)
            logger.info(f"[直连控制] 手机已断开: {addr}")

    async def 服务循环(self) -> None:
        """启动 WebSocket 服务并持续运行，直到协程被取消"""
        try:
            from websockets.asyncio.server import serve  # websockets >= 14
        except ImportError:
            from websockets.server import serve  # type: ignore[no-redef]

        async with serve(self._处理连接, "0.0.0.0", DIRECT_CONTROL_PORT) as server:
            self._server = server
            logger.info(f"[直连控制] 本地控制服务已启动，端口: {DIRECT_CONTROL_PORT}")
            try:
                await server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("[直连控制] 本地控制服务已停止")
