"""
机器狗客户端
功能:
- 配置管理（~/sparkrobot/config/config.toml）
- 配置热更新（watchdog 监听）
- WebSocket 通信
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- HTTP API服务（拍照等功能）
- 日志记录
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from sparkrobot_common import WORKSPACE_DIR, configure_logger, 检测机器人运控版本

from core.config import Config
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
    构建拍照响应消息,
)
from modules.transport.ws_manager import WebSocketManager
from modules.vision.camera import capture_photo

APP_NAME = "robot-agent"


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

        # 初始化配置
        self.config_store = Config.instance(workspace)
        self.config = self.config_store.get()

        # 设置日志
        self._初始化日志()

        # 启动配置文件监听（热更新）
        if self.config_store.启动监听():
            self.logger.info("配置文件监听已启动")
            self.config_store.注册配置变更回调(self._处理配置变化)
        else:
            self.logger.warning("配置文件监听启动失败，热更新功能不可用")

        self.ws_manager = WebSocketManager(self.config)
        self.process_controller = ProcessController()
        self.joystick_controller = JoystickController(self.process_controller)
        self._action_executor = ThreadPoolExecutor(max_workers=1)
        self.audio_task: Optional[asyncio.Task] = None
        self._ipc_status_task: Optional[asyncio.Task] = None
        self._ipc_status_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        """ 初始化音频捕获 """
        self.audio_capture = AudioCapture(
            self.config,
            is_connected=lambda: self.ws_manager.connected,
            is_upload_connected=lambda: self.ws_manager.connected_audio_upload,
            send_audio_start=self.发送音频开始,
            # send_audio_chunk=self.发送音频帧,
            send_audio_chunk=self.发送音频数据块,
            send_audio_end=self.发送音频结束,
        )

        """ 初始化 IPC 服务器 """
        self.ipc_server = IpcServer(self.project_name, self._处理IPC状态)

        """ 初始化消息处理函数 """
        self.message_handlers: Dict[str, Callable] = {
            "text_response": self._处理文本响应,
            "audio_response": self._处理音频响应并播放,
            "action_command": self._处理动作指令,
            "control_command": self._处理控制指令,
            "audio_control": self._处理音频控制,
            "stop_audio": self._处理停止音频播放,
            "error": self._处理服务器错误,
            "audio_stream_start": self._处理音频流开始,
            "audio_stream_chunk": self._处理音频流数据块,
            "audio_stream_end": self._处理音频流结束,
            "camera_capture": self._处理相机拍照,
        }

        """ 初始化动作执行函数 """
        self.action_executor: Optional[Callable] = None

        """ 初始化机器人版本 """
        version = 检测机器人运控版本()
        if version:
            # 使用新的扁平化配置格式
            self.config_store.设置("robot.version", version)
            self.config = self.config_store.get()

        # 重连策略配置
        self.initial_reconnect_interval = self.config["server"].get("reconnect_interval", 5)
        self.max_reconnect_interval = 60
        self.current_reconnect_interval = self.initial_reconnect_interval

    def _处理配置变化(self, new_config: Dict[str, Any]) -> None:
        """配置变更回调"""
        self.logger.info("检测到配置变更，正在更新...")
        self.config = new_config
        # 更新相关组件的配置
        self.ws_manager.config = new_config
        self.audio_capture.config = new_config
        # 更新重连间隔
        self.initial_reconnect_interval = self.config["server"].get("reconnect_interval", 5)


    def _初始化日志(self) -> None:
        """ 初始化日志记录 """
        logging_cfg = self.config.get("logging", {})
        level = logging_cfg.get("level", "INFO")
        max_file_size_mb = logging_cfg.get("max_file_size_mb")
        self.logger = configure_logger(
            app_name=self.project_name,
            log_dir=self.log_dir,
            level=level,
            max_file_size_mb=max_file_size_mb,
            log_file_prefix="application",
        )

    async def 连接到服务器(self) -> bool:
        """连接到服务器"""
        robot_uuid = self.config["robot"]["uuid"]
        success = await self.ws_manager.连接(robot_uuid)
        if success:
            await self.发送注册()
            # 确保注册消息发送后连接仍然有效
            if not self.ws_manager.connected:
                return False
        return success

    async def 断开连接到服务器(self, shutdown_resources: bool = False) -> None:
        """断开连接"""
        await self.ws_manager.断开连接()
        if shutdown_resources:
            self.process_controller.关闭()
            if self._action_executor:
                self._action_executor.shutdown(wait=False)

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

    async def 发送拍照响应(
        self, request_id: str, success: bool, image: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """发送拍照响应消息"""
        message = 构建拍照响应消息(
            self.config["robot"]["uuid"], request_id, success, image, error
        )
        await self.发送消息(message, channel="business")

    async def _处理IPC状态(self, status_msg: Dict[str, Any]) -> None:
        await self._ipc_status_queue.put(status_msg)

    async def _发送IPC状态循环(self) -> None:
        while True:
            status_msg = await self._ipc_status_queue.get()
            if not self.ws_manager.connected and not self.ws_manager.connected_control:
                continue
            await self.发送状态(status_msg)

    async def _处理相机拍照(self, data: Dict[str, Any]) -> None:
        """处理相机拍照消息"""
        request_id = data.get("requestId", "")
        self.logger.info(f"收到拍照请求: {request_id}")
        
        try:
            # 在线程池中执行拍照，避免阻塞
            loop = asyncio.get_event_loop()
            rtsp_url = "rtsp://127.0.0.1:8554/test"
            image_base64 = await loop.run_in_executor(
                None, capture_photo, rtsp_url, 5
            )
            
            if image_base64:
                # 发送拍照成功响应
                await self.发送拍照响应(request_id, True, image_base64)
                self.logger.info(f"拍照成功: {request_id}")
            else:
                # 发送拍照失败响应
                await self.发送拍照响应(request_id, False, None, "拍照失败")
                self.logger.error(f"拍照失败: {request_id}")
                
        except Exception as e:
            self.logger.error(f"处理拍照请求时出错: {e}", exc_info=True)
            await self.发送拍照响应(request_id, False, None, str(e))

    async def _处理文本响应(self, data: Dict[str, Any]) -> None:
        """ 处理文本响应消息 """
        await 处理文本响应(data, self.action_executor, self._确保动作执行器())

    async def _处理音频控制(self, data: Dict[str, Any]) -> None:
        """ 处理音频控制消息 """
        if "enabled" in data:
            enabled = bool(data.get("enabled", True))
            self.audio_capture.audio_streaming_enabled = enabled
            self.logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def _处理音频响应并播放(self, data: Dict[str, Any]) -> None:
        """ 处理音频响应消息 """
        处理音频响应并播放(data)

    async def _处理停止音频播放(self, data: Dict[str, Any]) -> None:
        """ 处理停止音频播放消息 """
        停止当前音频播放()

    async def _处理动作指令(self, data: Dict[str, Any]) -> None:
        await 处理动作指令(data, self.action_executor, self._确保动作执行器())

    async def _处理控制指令(self, data: Dict[str, Any]) -> None:
        """ 处理控制指令消息 """
        self.joystick_controller.处理命令(data)

    async def _处理服务器错误(self, data: Dict[str, Any]) -> None:
        """ 处理服务器错误消息 """
        code = data.get("code", "")
        message = data.get("message", "")
        self.logger.error(f"服务器错误: {code} - {message}")

    async def _处理音频流开始(self, data: Dict[str, Any]) -> None:
        """ 处理音频流开始消息 """
        self.logger.debug("音频流开始")

    async def _处理音频流数据块(self, data: Dict[str, Any]) -> None:
        """ 处理音频流数据块消息 """
        # 音频流数据块由底层处理，这里不需要额外处理
        pass

    async def _处理音频流结束(self, data: Dict[str, Any]) -> None:
        """ 处理音频流结束消息 """
        self.logger.debug("音频流结束")

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

                    # 使用 ALL_COMPLETED 模式，只有所有任务都完成才会返回
                    # 单个次要通道断开不会影响其他任务，它们会在后台自动重连
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

                    # 检查是否有任务因异常退出
                    should_reconnect = False
                    for task in done:
                        try:
                            if not task.cancelled():
                                exc = task.exception()
                                if exc:
                                    self.logger.warning(f"子任务异常退出: {exc}")
                                    should_reconnect = True
                        except Exception as e:
                            self.logger.warning(f"子任务退出: {e}")
                            should_reconnect = True

                    # 只有主连接（business）断开才需要完全重连
                    if not self.ws_manager.connected:
                        should_reconnect = True
                        self.logger.info("主连接已断开，准备重连...")

                    if should_reconnect:
                        # 取消剩余任务
                        for task in pending:
                            task.cancel()

                        # 等待剩余任务取消完成
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)

                        self.logger.info("任务组结束，准备重连...")
                    else:
                        # 所有任务正常结束，继续运行
                        self.logger.debug("所有任务正常结束")

                except KeyboardInterrupt:
                    self.logger.info("收到中断信号，正在退出...")
                    break
                except Exception as e:
                    self.logger.error(f"运行时错误: {e}")
                    self.ws_manager.connected = False
                finally:
                    if self._是否有活跃的WebSocket连接():
                        await self.断开连接到服务器(shutdown_resources=False)
        except asyncio.CancelledError:
            self.logger.info("收到中断信号，正在退出...")
        finally:
            await self.断开连接到服务器(shutdown_resources=True)
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

        success = await self.连接到服务器()
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
        if not self._ipc_status_task or self._ipc_status_task.done():
            self._ipc_status_task = asyncio.create_task(self._发送IPC状态循环())
        tasks.append(self._ipc_status_task)
        tasks.append(
            asyncio.create_task(self.ws_manager.发送心跳消息循环(self.config["robot"]["uuid"], 构建心跳消息))
        )
        return tasks

    def _确保动作执行器(self) -> ThreadPoolExecutor:
        if not self._action_executor or getattr(self._action_executor, "_shutdown", False):
            self._action_executor = ThreadPoolExecutor(max_workers=1)
        return self._action_executor

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
            停止当前音频播放()
        except Exception:
            pass
        try:
            # 停止配置文件监听
            self.config_store.停止监听()
            self.logger.info("配置文件监听已停止")
        except Exception:
            pass

class 动作执行器:
    def __init__(self, client: "RobotClient") -> None:
        self.client = client
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
        if action in ["shake_hand", "nod"]:
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
        """ 执行动作(操作机器人行动的动作) """
        try:
            token = self._下一个_token()
            self.client.logger.debug(f"开始执行动作: {action}, 参数: {parameters}")
            self._停止当前动作()
            # 特殊处理move动作
            if action == "move":
                # 将参数编码为JSON并发送
                command = json.dumps({
                    "type": "ai_move", # 使用type，通过控制指令执行，而不是使用action
                    "vx": parameters.get("vx", 0),
                    "vy": parameters.get("vy", 0),
                    "yaw_rate": parameters.get("yaw_rate", 0),
                    "duration": parameters.get("duration", 2),
                })
                wait_time = float(parameters.get("duration", 2)) #  + 0.5  # 多等0.5秒确保完成
            else:
                # 其他动作的处理
                command = action
                wait_time = self._解析等待时间(action)
            if not command:
                self.client.logger.warning(f"不支持的动作: {action}")
                return False
            success = self.client.发送命令到交互式进程(command)
            if not success:
                self.client.logger.error(f"发送命令 {command} 失败")
                return False
            completed = self._可中断的睡眠(token, wait_time)
            if not completed:
                self.client.logger.info(f"动作 {action} 被打断")
                return False
            self.client.logger.debug(f"动作 {action} 执行完成")
            return True
        except Exception as e:
            self.client.logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False

async def main():
    """主函数"""
    client = RobotClient()

    # get modules/actions/executor.py 的路径
    script_dir = Path(__file__).parent
    interactive_script = script_dir / "modules" / "actions" / "executor.py"

    if not interactive_script.exists():
        client.logger.error(f"找不到交互式脚本: {interactive_script}")
        return

    # 启动交互式子进程
    if not client.启动交互式进程(str(interactive_script)):
        client.logger.error("无法启动交互式子进程")
        return

    client.设置动作执行器(动作执行器(client).执行动作)

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
