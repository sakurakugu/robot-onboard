#!/usr/bin/env python3
"""
机器狗客户端
功能：
- 配置管理（~/sparkrobot/config/robot-agent.toml）
- WebSocket 通信
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- 日志记录
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.config import APP_NAME, WORKSPACE_DIR, Config
from core.logger import configure_logger
from core.utils import 检测机器人运控版本
from modules.actions.mapping import 处理动作指令, 处理文本响应
from modules.audio.capture import AudioCapture
from modules.audio.playback import 停止当前音频播放, 处理音频响应并播放
from modules.control.ipc import IpcServer
from modules.control.joystick import JoystickController
from modules.control.process import ProcessController
from modules.transport.protocol import (
    构建心跳消息,
    构建文本输入消息,
    构建机器人注册消息,
    构建状态消息,
    构建音频帧消息,
    构建音频开始消息,
    构建音频结束消息,
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
        self.project_name = APP_NAME
        self.log_dir = workspace / "logs" / self.project_name

        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.config_store = Config.instance(workspace, self.project_name)
        self.config = self.config_store.get()

        # 设置日志
        self._初始化日志()

        self.ws_manager = WebSocketManager(self.config, self.logger)
        self.process_controller = ProcessController(self.logger)
        self.joystick_controller = JoystickController(self.process_controller, self.logger)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.audio_task: Optional[asyncio.Task] = None

        """ 初始化音频捕获 """
        self.audio_capture = AudioCapture(
            self.config,
            self.logger,
            is_connected=lambda: self.ws_manager.connected,
            is_upload_connected=lambda: self.ws_manager.connected_audio_upload,
            send_audio_start=self.发送音频开始,
            # send_audio_chunk=self.发送音频帧,
            send_audio_chunk=self.发送音频数据块,
            send_audio_end=self.发送音频结束,
        )

        """ 初始化 IPC 服务器 """
        self.ipc_server = IpcServer(self.project_name, self.logger, self.发送状态)

        """ 初始化消息处理函数 """
        self.message_handlers: Dict[str, Callable] = {
            "text_response": self._处理文本响应,
            "audio_response": self._处理音频响应并播放,
            "action_command": self._处理动作指令,
            "control_command": self._处理控制指令,
            "audio_control": self._处理音频控制,
            "stop_audio": self._处理停止音频播放,
            "error": self._处理服务器错误,
        }

        """ 初始化动作执行函数 """
        self.action_executor: Optional[Callable] = None

        """ 初始化机器人版本 """
        version = 检测机器人运控版本()
        if version:
            self.config.setdefault("robot", {})
            self.config["robot"]["version"] = version
            self.config_store.save(self.config)

        # 重连策略配置
        self.initial_reconnect_interval = self.config["server"].get("reconnect_interval", 5)
        self.max_reconnect_interval = 60
        self.current_reconnect_interval = self.initial_reconnect_interval


    def _初始化日志(self) -> None:
        """ 初始化日志记录 """
        logging_cfg = self.config.get("logging", {})
        level = logging_cfg.get("level", "INFO")
        max_file_size_mb = logging_cfg.get("max_file_size_mb")
        self.logger = configure_logger(
            self.log_dir,
            level=level,
            max_file_size_mb=max_file_size_mb,
            log_file_prefix="application",
        )

    async def connect(self) -> bool:
        """连接到服务器"""
        robot_uuid = self.config["robot"]["uuid"]
        success = await self.ws_manager.连接(robot_uuid)
        if success:
            await self.发送注册()
            # 确保注册消息发送后连接仍然有效
            if not self.ws_manager.connected:
                return False
        return success

    async def disconnect(self) -> None:
        """断开连接"""
        await self.ws_manager.断开连接()
        self.process_controller.关闭()
        self._executor.shutdown(wait=False)

    async def 发送消息(self, message: Dict[str, Any], channel: str = "business") -> None:
        """发送消息到服务器"""
        await self.ws_manager.发送消息(message, channel=channel)

    async def 发送文本(self, text: str) -> None:
        message = 构建文本输入消息(self.config["robot"]["uuid"], text)
        await self.发送消息(message, channel="business")

    async def 发送音频开始(self, session_id: str, frame_duration_ms: int) -> None:
        """ 发送音频开始消息 """
        message = 构建音频开始消息(
            self.config["robot"]["uuid"],
            session_id,
            frame_duration_ms,
            int(self.config["audio"].get("sample_rate", 16000)),
            int(self.config["audio"].get("channels", 1)),
        )
        await self.发送消息(message, channel="audio_upload")

    async def 发送音频数据块(self, session_id: str, seq: int, audio_bytes: bytes, frame_duration_ms: int) -> None:
        """ 发送音频数据块消息 """
        message = 构建音频帧消息(
            self.config["robot"]["uuid"],
            session_id,
            seq,
            audio_bytes,
            frame_duration_ms,
            int(self.config["audio"].get("sample_rate", 16000)),
            int(self.config["audio"].get("channels", 1)),
        )
        await self.发送消息(message, channel="audio_upload")

    async def 发送音频结束(self, session_id: str, reason: str) -> None:
        """ 发送音频结束消息 """
        message = 构建音频结束消息(self.config["robot"]["uuid"], session_id, reason)
        await self.发送消息(message, channel="audio_upload")

    async def 发送注册(self) -> None:
        """ 发送注册消息 """
        message = 构建机器人注册消息(
            self.config["robot"]["uuid"],
            self.config["robot"]["name"],
            self.config["robot"]["model"],
            self.config["robot"]["version"],
        )
        await self.发送消息(message, channel="business")

    async def 发送心跳(self) -> None:
        """ 发送心跳消息 """
        message = 构建心跳消息(self.config["robot"]["uuid"])
        if self.ws_manager.connected_control:
            await self.发送消息(message, channel="control")
        else:
            await self.发送消息(message, channel="business")

    async def 发送状态(self, status_msg: Dict[str, Any]) -> None:
        """ 发送状态消息 """
        message = 构建状态消息(
            self.config["robot"]["uuid"], status_msg.get("seq"), status_msg.get("data", {})
        )
        await self.发送消息(message, channel="control")

    async def _处理文本响应(self, data: Dict[str, Any]) -> None:
        """ 处理文本响应消息 """
        await 处理文本响应(data, self.logger, self.action_executor, self._executor)

    async def _处理音频控制(self, data: Dict[str, Any]) -> None:
        """ 处理音频控制消息 """
        enabled = bool(data.get("enabled", True))
        self.audio_capture.audio_streaming_enabled = enabled
        self.logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def _处理音频响应并播放(self, data: Dict[str, Any]) -> None:
        """ 处理音频响应消息 """
        处理音频响应并播放(data, self.logger, self.log_dir / "media")

    async def _处理停止音频播放(self, data: Dict[str, Any]) -> None:
        """ 处理停止音频播放消息 """
        停止当前音频播放(self.logger)

    async def _处理动作指令(self, data: Dict[str, Any]) -> None:
        await 处理动作指令(data, self.logger, self.action_executor, self._executor)

    async def _处理控制指令(self, data: Dict[str, Any]) -> None:
        """ 处理控制指令消息 """
        self.joystick_controller.处理命令(data)

    async def _处理服务器错误(self, data: Dict[str, Any]) -> None:
        """ 处理服务器错误消息 """
        code = data.get("code", "")
        message = data.get("message", "")
        self.logger.error(f"服务器错误: {code} - {message}")

    async def _处理收到的消息(self, message: Dict[str, Any]) -> None:
        """ 处理收到的消息 """
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

    async def 运行(self) -> None:
        """ 运行机器狗客户端 """
        self.logger.info("机器狗客户端启动")
        await self.ipc_server.启动()
        try:
            while True:
                try:
                    if not await self._确保与服务器连接():
                        continue
                    tasks = self._构建异步任务()
                    
                    if not tasks:
                        await asyncio.sleep(1)
                        continue

                    # 等待任意一个任务完成
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                    # 记录退出的任务
                    for task in done:
                        try:
                            if not task.cancelled():
                                task.result()
                        except Exception as e:
                            self.logger.warning(f"子任务退出: {e}")

                    # 取消剩余任务
                    for task in pending:
                        task.cancel()
                    
                    # 等待剩余任务取消完成
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)

                    self.logger.info("任务组结束，准备重连...")
                except KeyboardInterrupt:
                    self.logger.info("收到中断信号，正在退出...")
                    break
                except Exception as e:
                    self.logger.error(f"运行时错误: {e}")
                    self.ws_manager.connected = False
                finally:
                    if self._是否有活跃的WebSocket连接():
                        await self.disconnect()
        except asyncio.CancelledError:
            self.logger.info("收到中断信号，正在退出...")
        finally:
            await self.ipc_server.关闭()
            try:
                await self.取消初始化()
            except Exception:
                pass
            self.logger.info("客户端已关闭")

    async def _确保与服务器连接(self) -> bool:
        """ 确保与服务器连接 """
        if self.ws_manager.connected:
            # 连接正常，重置重连间隔
            self.current_reconnect_interval = self.initial_reconnect_interval
            return True

        success = await self.connect()
        if success:
            self.current_reconnect_interval = self.initial_reconnect_interval
            return True

        self.logger.info(f"{self.current_reconnect_interval} 秒后重试连接...")
        await asyncio.sleep(self.current_reconnect_interval)

        # 指数退避，最大不超过 max_reconnect_interval
        self.current_reconnect_interval = min(
            self.current_reconnect_interval * 2,
            self.max_reconnect_interval
        )
        return False

    def _构建异步任务(self) -> list[asyncio.Task]:
        """ 构建要运行的异步任务 """
        tasks: list[asyncio.Task] = []
        if self.ws_manager.ws_business and self.ws_manager.connected:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.接受消息循环("business", self.ws_manager.ws_business, self._处理收到的消息)
                )
            )
        if self.ws_manager.ws_control and self.ws_manager.connected_control:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.接受消息循环("control", self.ws_manager.ws_control, self._处理收到的消息)
                )
            )
        if self.ws_manager.ws_audio_download and self.ws_manager.connected_audio_download:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.接受消息循环(
                        "audio_download", self.ws_manager.ws_audio_download, self._处理收到的消息
                    )
                )
            )
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self.audio_capture.开始采集())
        tasks.append(self.audio_task)
        tasks.append(
            asyncio.create_task(self.ws_manager.发送心跳消息循环(self.config["robot"]["uuid"], 构建心跳消息))
        )
        return tasks

    def _是否有活跃的WebSocket连接(self) -> bool:
        """ 检查是否有活动的 WebSocket 连接 """
        return bool(
            self.ws_manager.ws_business
            or self.ws_manager.ws_control
            or self.ws_manager.ws_audio_download
            or self.ws_manager.ws_audio_upload
        )

    def 设置动作执行器(self, executor: Callable) -> None:
        """ 设置动作执行器 """
        self.action_executor = executor

    def 启动交互式进程(self, script_path: str) -> bool:
        """ 启动交互式进程 """
        return self.process_controller.启动(script_path)

    def 发送命令到交互式进程(self, command: str) -> bool:
        """ 发送命令到交互式进程 """
        return self.process_controller.发送命令(command)

    async def 取消初始化(self) -> None:
        """ 取消初始化客户端 """
        try:
            停止当前音频播放(self.logger)
        except Exception:
            pass
        try:
            self.config_store.save(self.config)
            self.logger.info("配置已保存")
        except Exception:
            self.logger.warning("配置保存失败")

def _构建动作映射() -> Dict[str, str]:
    """ 构建动作映射 """
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
        "cancel_two_leg_stand": "cancel_two_leg_stand",
    }


class ActionRunner:
    def __init__(self, client: "RobotClient", action_map: Dict[str, str]) -> None:
        self.client = client
        self.action_map = action_map
        self._current_token = 0

    def _下一个_token(self) -> int:
        """ 生成下一个令牌 """
        self._current_token += 1
        return self._current_token

    def _停止当前动作(self) -> None:
        """ 停止当前动作 """
        try:
            self.client.发送命令到交互式进程(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
            self.client.发送命令到交互式进程(
                json.dumps({
                    "type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0
                })
            )
        except Exception:
            pass

    def _解析等待时间(self, action: str) -> float:
        """ 解析动作等待时间 """
        if action in ["walk_forward", "walk_backward", "turn_left", "turn_right"]:
            return 2.5
        if action in ["shake_hand", "nod", "wave"]:
            return 4.5
        if action == "dance":
            return 5.0
        return 3.5

    def _可中断的睡眠(self, token: int, seconds: float) -> bool:
        """ 可中断的睡眠 """
        end_time = time.time() + seconds
        while time.time() < end_time:
            if token != self._current_token:
                return False
            time.sleep(0.1)
        return True

    def 执行动作(self, action: str, parameters: dict) -> bool:
        """ 执行动作 """
        try:
            token = self._下一个_token()
            self.client.logger.debug(f"开始执行动作: {action}")
            self._停止当前动作()
            command = self.action_map.get(action)
            if not command:
                self.client.logger.warning(f"不支持的动作: {action}")
                return False
            success = self.client.发送命令到交互式进程(command)
            if not success:
                self.client.logger.error(f"发送命令 {command} 失败")
                return False
            wait_time = self._解析等待时间(action)
            completed = self._可中断的睡眠(token, wait_time)
            if not completed:
                self.client.logger.info(f"动作 {action} 被打断")
                return False
            self.client.logger.debug(f"动作 {action} 执行完成")
            return True
        except Exception as e:
            self.client.logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False


def _构建动作执行器(client: "RobotClient", action_map: Dict[str, str]) -> Callable[[str, dict], bool]:
    """ 构建动作执行器 """
    runner = ActionRunner(client, action_map)
    return runner.执行动作


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
    if not client.启动交互式进程(str(interactive_script)):
        client.logger.error("无法启动交互式子进程")
        return

    client.设置动作执行器(_构建动作执行器(client, _构建动作映射()))

    # 运行客户端
    try:
        await client.运行()
    except KeyboardInterrupt:
        client.logger.info("客户端已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
