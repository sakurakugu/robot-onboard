#!/usr/bin/env python3
"""
机器狗客户端
功能：
- 配置管理（~/sparkrobot/config/robot-chat.toml）
- WebSocket 通信
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- 日志记录
"""

import asyncio
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.config import WORKSPACE_DIR, Config
from core.logger import configure_logger
from modules.actions.mapping import handle_action_command, handle_text_response
from modules.audio.capture import AudioCapture
from modules.audio.playback import handle_audio_response, stop_audio_playback
from modules.control.ipc import IpcServer
from modules.control.process import ProcessController
from modules.transport.protocol import (
    build_audio_chunk,
    build_audio_end,
    build_audio_start,
    build_heartbeat,
    build_robot_register,
    build_status,
    build_text_input,
)
from modules.transport.ws_manager import WebSocketManager


class RobotClient:
    """机器狗客户端"""

    def __init__(self, workspace: Optional[Path] = None):
        """初始化客户端

        Args:
            workspace: 工作目录，默认为 ~/sparkrobot
        """
        # 配置目录
        if workspace is None:
            workspace = WORKSPACE_DIR
        self.project_name = "robot-agent"
        self.log_dir = workspace / "logs" / self.project_name

        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.config_store = Config.instance(workspace, self.project_name)
        self.config = self.config_store.get()

        # 设置日志
        self._setup_logger()

        self.ws_manager = WebSocketManager(self.config, self.logger)
        self.process_controller = ProcessController(self.logger)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.audio_task: Optional[asyncio.Task] = None

        self.audio_capture = AudioCapture(
            self.config,
            self.logger,
            is_connected=lambda: self.ws_manager.connected,
            is_upload_connected=lambda: self.ws_manager.connected_audio_upload,
            send_audio_start=self.send_audio_start,
            send_audio_chunk=self.send_audio_chunk,
            send_audio_end=self.send_audio_end,
        )

        self.ipc_server = IpcServer(self.project_name, self.logger, self.send_status)

        self.message_handlers: Dict[str, Callable] = {
            "text_response": self._handle_text_response,
            "audio_response": self._handle_audio_response,
            "action_command": self._handle_action_command,
            "control_command": self._handle_control_command,
            "audio_control": self._handle_audio_control,
            "stop_audio": self._handle_stop_audio,
            "error": self._handle_error,
        }

        self.action_executor: Optional[Callable] = None

        version = self._detect_robot_version()
        if version:
            self.config.setdefault("robot", {})
            self.config["robot"]["version"] = version
            self.config_store.save(self.config)

    def _detect_robot_version(self) -> Optional[str]:
        try:
            result = subprocess.run(
                "grep -oP 'motion-control_\\K[^_]+' /etc/release/*[^rootfs]*.yaml",
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out = result.stdout.strip()
            if not out:
                return None
            for line in out.splitlines():
                ver = line.rsplit(":", 1)[-1].strip()
                if ver:
                    return ver
            return None
        except Exception:
            return None


    def _setup_logger(self) -> None:
        logging_cfg = self.config.get("logging", {})
        level = logging_cfg.get("level", "INFO")
        max_file_size_mb = logging_cfg.get("max_file_size_mb")
        self.logger = configure_logger(self.log_dir, level=level, max_file_size_mb=max_file_size_mb)

    async def connect(self) -> bool:
        """连接到服务器"""
        robot_uuid = self.config["robot"]["uuid"]
        success = await self.ws_manager.connect(robot_uuid)
        if success:
            await self.send_register()
        return success

    async def disconnect(self) -> None:
        """断开连接"""
        await self.ws_manager.disconnect()
        self.process_controller.stop()
        self._executor.shutdown(wait=False)

    async def send_message(self, message: Dict[str, Any], channel: str = "business") -> None:
        """发送消息到服务器"""
        await self.ws_manager.send_message(message, channel=channel)

    async def send_text(self, text: str) -> None:
        message = build_text_input(self.config["robot"]["uuid"], text)
        await self.send_message(message, channel="business")

    async def send_audio_start(self, session_id: str, frame_duration_ms: int) -> None:
        message = build_audio_start(
            self.config["robot"]["uuid"],
            session_id,
            frame_duration_ms,
            int(self.config["audio"].get("sample_rate", 16000)),
            int(self.config["audio"].get("channels", 1)),
        )
        await self.send_message(message, channel="audio_upload")

    async def send_audio_chunk(self, session_id: str, seq: int, audio_bytes: bytes, frame_duration_ms: int) -> None:
        message = build_audio_chunk(
            self.config["robot"]["uuid"],
            session_id,
            seq,
            audio_bytes,
            frame_duration_ms,
            int(self.config["audio"].get("sample_rate", 16000)),
            int(self.config["audio"].get("channels", 1)),
        )
        await self.send_message(message, channel="audio_upload")

    async def send_audio_end(self, session_id: str, reason: str) -> None:
        message = build_audio_end(self.config["robot"]["uuid"], session_id, reason)
        await self.send_message(message, channel="audio_upload")

    async def send_register(self) -> None:
        message = build_robot_register(
            self.config["robot"]["uuid"],
            self.config["robot"].get("name"),
            self.config["robot"].get("model"),
            self.config["robot"].get("version", "0.0.0"),
        )
        await self.send_message(message, channel="business")

    async def send_heartbeat(self) -> None:
        message = build_heartbeat(self.config["robot"]["uuid"])
        if self.ws_manager.connected_control:
            await self.send_message(message, channel="control")
        else:
            await self.send_message(message, channel="business")

    async def send_status(self, status_msg: Dict[str, Any]) -> None:
        message = build_status(
            self.config["robot"]["uuid"], status_msg.get("seq"), status_msg.get("data", {})
        )
        await self.send_message(message, channel="control")

    async def _handle_text_response(self, data: Dict[str, Any]) -> None:
        await handle_text_response(data, self.logger, self.action_executor, self._executor)

    async def _handle_audio_control(self, data: Dict[str, Any]) -> None:
        enabled = bool(data.get("enabled", True))
        self.audio_capture.audio_streaming_enabled = enabled
        self.logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def _handle_audio_response(self, data: Dict[str, Any]) -> None:
        handle_audio_response(data, self.logger, self.log_dir / "media")

    async def _handle_stop_audio(self, data: Dict[str, Any]) -> None:
        stop_audio_playback(self.logger)

    async def _handle_action_command(self, data: Dict[str, Any]) -> None:
        await handle_action_command(data, self.logger, self.action_executor, self._executor)

    async def _handle_control_command(self, data: Dict[str, Any]) -> None:
        command = data.get("command")
        mode = data.get("mode", "move")
        channel = data.get("channel")
        x = float(data.get("x", 0) or 0)
        y = float(data.get("y", 0) or 0)
        speed = float(data.get("speed", 5) or 5)

        self.logger.debug(
            f"收到控制指令: command={command}, mode={mode}, channel={channel}, x={x}, y={y}, speed={speed}"
        )

        if not command:
            return

        if command == "estop":
            self.process_controller.send_command(json.dumps({"type": "estop"}))
            return

        # 归一化速度倍率（1-10）
        speed_ratio = max(0.0, min(1.0, speed / 10.0))

        if command == "joystick":
            if mode == "pose" or channel == "pose":
                max_roll = 0.5
                max_pitch = 0.5
                roll_rate = y * max_roll * speed_ratio
                pitch_rate = -x * max_pitch * speed_ratio
                payload = {
                    "type": "attitude",
                    "roll_rate": roll_rate,
                    "pitch_rate": pitch_rate,
                    "yaw_rate": 0.0,
                    "height_vel": 0.0,
                }
                self.process_controller.send_command(json.dumps(payload))
                return

            # move 模式
            max_vx = 0.6
            max_vy = 0.4
            max_yaw = 0.6

            if channel == "look":
                payload = {
                    "type": "move",
                    "vx": 0.0,
                    "vy": 0.0,
                    "yaw_rate": y * max_yaw * speed_ratio,
                }
                self.process_controller.send_command(json.dumps(payload))
                return

            payload = {
                "type": "move",
                "vx": x * max_vx * speed_ratio,
                "vy": y * max_vy * speed_ratio,
                "yaw_rate": 0.0,
            }
            self.process_controller.send_command(json.dumps(payload))
            return

        if command == "joystick_stop":
            if mode == "pose" or channel == "pose":
                self.process_controller.send_command(
                    json.dumps(
                        {"type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0}
                    )
                )
                return

            self.process_controller.send_command(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
            return

    async def _handle_error(self, data: Dict[str, Any]) -> None:
        code = data.get("code", "")
        message = data.get("message", "")
        self.logger.error(f"服务器错误: {code} - {message}")

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        if not isinstance(msg_type, str):
            self.logger.warning(f"未知的消息类型: {msg_type}")
            return
        data = message.get("data", {})
        if not isinstance(data, dict):
            data = {}
        handler = self.message_handlers.get(msg_type)
        if handler:
            await handler(data)
        else:
            self.logger.warning(f"未知的消息类型: {msg_type}")

    async def run(self) -> None:
        self.logger.info("机器狗客户端启动")
        await self.ipc_server.start()
        while True:
            try:
                if not await self._ensure_connected():
                    continue
                tasks = self._build_tasks()
                await asyncio.gather(*tasks)
            except KeyboardInterrupt:
                self.logger.info("收到中断信号，正在退出...")
                break
            except Exception as e:
                self.logger.error(f"运行时错误: {e}")
                self.ws_manager.connected = False
            finally:
                if self._has_active_ws():
                    await self.disconnect()
        await self.ipc_server.stop()

    async def _ensure_connected(self) -> bool:
        if self.ws_manager.connected:
            return True
        success = await self.connect()
        if success:
            return True
        reconnect_interval = self.config["server"].get("reconnect_interval", 5)
        self.logger.info(f"{reconnect_interval} 秒后重试连接...")
        await asyncio.sleep(reconnect_interval)
        return False

    def _build_tasks(self) -> list[asyncio.Task]:
        tasks: list[asyncio.Task] = []
        if self.ws_manager.ws_business and self.ws_manager.connected:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.receive_loop("business", self.ws_manager.ws_business, self._handle_message)
                )
            )
        if self.ws_manager.ws_control and self.ws_manager.connected_control:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.receive_loop("control", self.ws_manager.ws_control, self._handle_message)
                )
            )
        if self.ws_manager.ws_audio_download and self.ws_manager.connected_audio_download:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.receive_loop(
                        "audio_download", self.ws_manager.ws_audio_download, self._handle_message
                    )
                )
            )
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self.audio_capture.run())
        tasks.append(self.audio_task)
        tasks.append(
            asyncio.create_task(self.ws_manager.heartbeat_loop(self.config["robot"]["uuid"], build_heartbeat))
        )
        return tasks

    def _has_active_ws(self) -> bool:
        return bool(
            self.ws_manager.ws_business
            or self.ws_manager.ws_control
            or self.ws_manager.ws_audio_download
            or self.ws_manager.ws_audio_upload
        )

    def set_action_executor(self, executor: Callable) -> None:
        self.action_executor = executor

    def start_interactive_process(self, script_path: str) -> bool:
        return self.process_controller.start(script_path)

    def send_command_to_process(self, command: str) -> bool:
        return self.process_controller.send_command(command)


def _build_action_map() -> Dict[str, str]:
    return {
        "stand_up": "stand_up",
        "sit_down": "sit_down",
        "walk_forward": "walk_forward",
        "walk_backward": "walk_backward",
        "turn_left": "turn_left",
        "turn_right": "turn_right",
        "dance": "dance",
        "jump": "jump",
        "front_jump": "front_jump",
        "backflip": "backflip",
        "shake_hand": "shake_hand",
        "nod": "nod",
        "wave": "wave",
        "two_leg_stand": "two_leg_stand",
    }


class ActionRunner:
    def __init__(self, client: "RobotClient", action_map: Dict[str, str]) -> None:
        self.client = client
        self.action_map = action_map
        self._current_token = 0

    def _next_token(self) -> int:
        self._current_token += 1
        return self._current_token

    def _stop_current(self) -> None:
        try:
            self.client.send_command_to_process(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
            self.client.send_command_to_process(
                json.dumps({
                    "type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0
                })
            )
        except Exception:
            pass

    def _resolve_wait(self, action: str) -> float:
        if action in ["walk_forward", "walk_backward", "turn_left", "turn_right"]:
            return 2.5
        if action in ["shake_hand", "nod", "wave"]:
            return 4.5
        if action == "dance":
            return 5.0
        return 3.5

    def _sleep_interruptible(self, token: int, seconds: float) -> bool:
        end_time = time.time() + seconds
        while time.time() < end_time:
            if token != self._current_token:
                return False
            time.sleep(0.1)
        return True

    def execute(self, action: str, parameters: dict) -> bool:
        try:
            token = self._next_token()
            self.client.logger.debug(f"开始执行动作: {action}")
            self._stop_current()
            command = self.action_map.get(action)
            if not command:
                self.client.logger.warning(f"不支持的动作: {action}")
                return False
            success = self.client.send_command_to_process(command)
            if not success:
                self.client.logger.error(f"发送命令 {command} 失败")
                return False
            wait_time = self._resolve_wait(action)
            completed = self._sleep_interruptible(token, wait_time)
            if not completed:
                self.client.logger.info(f"动作 {action} 被打断")
                return False
            self.client.logger.debug(f"动作 {action} 执行完成")
            return True
        except Exception as e:
            self.client.logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False


def _build_action_executor(client: "RobotClient", action_map: Dict[str, str]) -> Callable[[str, dict], bool]:
    runner = ActionRunner(client, action_map)
    return runner.execute


async def main():
    """主函数"""
    client = RobotClient()

    # 获取 modules/actions/executor.py 的路径
    script_dir = Path(__file__).parent
    interactive_script = script_dir / "modules" / "actions" / "executor.py"

    if not interactive_script.exists():
        client.logger.error(f"找不到交互式脚本: {interactive_script}")
        return

    # 启动交互式子进程
    if not client.start_interactive_process(str(interactive_script)):
        client.logger.error("无法启动交互式子进程")
        return

    client.set_action_executor(_build_action_executor(client, _build_action_map()))

    # 运行客户端
    try:
        await client.run()
    except KeyboardInterrupt:
        client.logger.info("客户端已停止")


if __name__ == "__main__":
    asyncio.run(main())
