"""
机器狗客户端
功能:
- 配置管理（~/sparkrobot/config/config.toml）
- 配置热更新（watchdog 监听）
- WebSocket 通信（云端服务器）
- 本地直连 WebSocket 控制服务（端口 8082，手机同局域网时直接发送指令，无需经过云端）
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

import httpx
from sparkrobot_common import WORKSPACE_DIR, configure_logger, get_logger, 检测机器人运控版本, 获取项目版本

from core.auth_client import get_auth_client
from core.config import Config
from modules.actions.mapping import 处理动作指令, 处理文本响应
from modules.audio.capture import AudioCapture
from modules.audio.playback import 停止当前音频播放, 处理音频响应并播放
from modules.control.ipc import IpcServer
from modules.control.joystick import JoystickController
from modules.control.process import ProcessController
from modules.control.ws_control_server import WsControlServer
from modules.transport.protocol import (
    构建SDK模式响应消息,
    构建心跳消息,
    构建拍照响应消息,
    构建文本输入消息,
    构建日志标记响应消息,
    构建机器人注册消息,
    构建状态消息,
    构建配置响应消息,
    构建音量响应消息,
    构建音频帧消息,
    构建音频开始消息,
    构建音频结束消息,
)
from modules.transport.ws_manager import WebSocketManager
from modules.vision.camera import capture_photo

from . import __version__ as ROBOT_AGENT_VERSION

APP_NAME = "robot-agent"
logger = get_logger(APP_NAME)

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
            logger.info("配置文件监听已启动")
            self.config_store.注册配置变更回调(self._处理配置变化)
        else:
            logger.warning("配置文件监听启动失败，热更新功能不可用")

        self.ws_manager = WebSocketManager(self.config)
        self.交互式子进程控制器 = ProcessController()
        self.joystick_controller = JoystickController(self.交互式子进程控制器)
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

        """ 初始化本地直连 WebSocket 控制服务器（手机同局域网时绕过云端） """
        self.ws_control_server = WsControlServer(
            self._处理直连控制指令,
            self._处理直连异步命令,
        )

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
            "volume_get": self._处理音量获取,
            "volume_set": self._处理音量设置,
            "volume_mute": self._处理设置静音,
            "config_get": self._处理配置获取,
            "config_update": self._处理配置更新,
            "sdk_mode_set": self._处理SDK模式设置,
            "sdk_mode_get": self._处理SDK模式获取,
            "log_mark": self._处理日志标记,
        }

        """ 初始化动作执行函数 """
        self.动作执行器: Optional[Callable] = None

        """ 初始化SDK模式状态 """
        self.sdk_mode_enabled = True  # 默认开启SDK模式
        self.last_action_before_disable: Optional[str] = None  # 关闭SDK时的最后动作

        """ 初始化机器人版本 """
        version = 检测机器人运控版本()
        self._motion_control_version = version or "unknown"
        if version:
            # 使用扁平化配置格式
            self.config_store.设置("robot.motion_control_version", version)

        agent_ver = ROBOT_AGENT_VERSION or "unknown"
        self._agent_version = agent_ver
        self.config_store.设置("robot.agent_version", agent_ver)
        self._robot_server_version = self._获取robot_server版本()
        self.config_store.设置("robot.server_version", self._robot_server_version)

        self.config = self.config_store.get()

        # 重连策略配置
        self.initial_reconnect_interval = self.config["server"].get("reconnect_interval", 5)
        self.max_reconnect_interval = 60
        self.current_reconnect_interval = self.initial_reconnect_interval

    def _处理配置变化(self, new_config: Dict[str, Any]) -> None:
        """配置变更回调"""
        logger.info("检测到配置变更，正在更新...")
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
        global logger
        logger = configure_logger(
            app_name=self.project_name,
            log_dir=self.log_dir,
            level=level,
            max_file_size_mb=max_file_size_mb,
            log_file_prefix="application",
        )

    def _获取robot_server版本(self) -> str:
        """获取本地 robot-server 版本号（优先 HTTP API，失败后读取包版本）"""
        try:
            token = get_auth_client().获取_token()
            cookies = {"session_token": token} if token else None
            with httpx.Client(timeout=2.0) as client:
                response = client.get("http://127.0.0.1:8080/api/v1/system/info", cookies=cookies)
                if response.status_code == 200:
                    payload = response.json()
                    info = payload.get("info", {}) if isinstance(payload, dict) else {}
                    ver = info.get("robot_server_version")
                    if isinstance(ver, str) and ver.strip():
                        return ver.strip()
        except Exception:
            pass

        project_root = Path(__file__).resolve().parents[1]
        return 获取项目版本(project_root.parent / "robot-server", "robot-server", "unknown")

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
            self.交互式子进程控制器.关闭()
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
        robot_cfg = self.config["robot"]
        message = 构建机器人注册消息(
            robot_cfg["uuid"],
            robot_cfg["name"],
            robot_cfg["model"],
            self._agent_version,
            {
                "agent_version": self._agent_version,
                "motion_control_version": self._motion_control_version,
                "robot_server_version": self._robot_server_version,
            },
        )
        await self.发送消息(message, channel="business")

    async def 发送心跳(self) -> None:
        """ 发送心跳消息 """
        message = 构建心跳消息(self.config["robot"]["uuid"])
        await self.发送消息(message, channel="business")

    async def 发送状态(self, status_msg: Dict[str, Any]) -> None:
        """ 发送状态消息 """
        message = 构建状态消息(
            self.config["robot"]["uuid"], status_msg.get("seq"), status_msg.get("data", {})
        )
        await self.发送消息(message, channel="business")

    async def 发送拍照响应(
        self, request_id: str, success: bool, image: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """发送拍照响应消息"""
        message = 构建拍照响应消息(
            self.config["robot"]["uuid"], request_id, success, image, error
        )
        await self.发送消息(message, channel="business")

    async def 发送音量响应(
        self, request_id: str, success: bool, data: Optional[Dict] = None, error: Optional[str] = None
    ) -> None:
        """发送音量响应消息"""
        message = 构建音量响应消息(
            self.config["robot"]["uuid"], request_id, success, data, error
        )
        await self.发送消息(message, channel="business")

    async def 发送配置响应(
        self, request_id: str, success: bool, data: Optional[Dict] = None, error: Optional[str] = None
    ) -> None:
        """发送配置响应消息"""
        message = 构建配置响应消息(
            self.config["robot"]["uuid"], request_id, success, data, error
        )
        await self.发送消息(message, channel="business")

    async def 发送SDK模式响应(
        self, request_id: str, success: bool, sdk_mode: Optional[bool] = None, error: Optional[str] = None
    ) -> None:
        """发送SDK模式响应消息"""
        message = 构建SDK模式响应消息(
            self.config["robot"]["uuid"], request_id, success, sdk_mode, error
        )
        await self.发送消息(message, channel="business")

    async def 发送日志标记响应(
        self, request_id: str, success: bool, marker: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """发送日志标记响应消息"""
        message = 构建日志标记响应消息(
            self.config["robot"]["uuid"], request_id, success, marker, error
        )
        await self.发送消息(message, channel="business")

    async def _处理IPC状态(self, status_msg: Dict[str, Any]) -> None:
        await self._ipc_status_queue.put(status_msg)

    def _获取认证cookies(self) -> dict:
        """获取认证 cookies"""
        token = get_auth_client().获取_token()
        return {"session_token": token} if token else {}

    async def _调用机器人服务器API(self, method: str, path: str, payload: dict | None = None) -> dict:
        """调用 robot-server HTTP API（127.0.0.1:8080）"""
        cookies = self._获取认证cookies()
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(
                    f"http://127.0.0.1:8080{path}", cookies=cookies, timeout=10.0
                )
            else:
                response = await client.post(
                    f"http://127.0.0.1:8080{path}", json=payload, cookies=cookies, timeout=10.0
                )
        return response.json()

    async def _发送IPC状态循环(self) -> None:
        while True:
            status_msg = await self._ipc_status_queue.get()
            if not self.ws_manager.connected:
                continue
            await self.发送状态(status_msg)

    async def _处理相机拍照(self, data: Dict[str, Any]) -> None:
        """处理相机拍照消息"""
        request_id = data.get("requestId", "")
        logger.info(f"收到拍照请求: {request_id}")

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
                logger.info(f"拍照成功: {request_id}")
            else:
                # 发送拍照失败响应
                await self.发送拍照响应(request_id, False, None, "拍照失败")
                logger.error(f"拍照失败: {request_id}")

        except Exception as e:
            logger.error(f"处理拍照请求时出错: {e}", exc_info=True)
            await self.发送拍照响应(request_id, False, None, str(e))

    async def _处理音量获取(self, data: Dict[str, Any]) -> None:
        """处理音量获取消息"""
        request_id = data.get("requestId", "")
        logger.info(f"收到音量获取请求: {request_id}")
        try:
            result = await self._调用机器人服务器API("GET", "/api/v1/volume")
            if result.get("success"):
                await self.发送音量响应(request_id, True, result.get("data"))
                logger.info(f"音量获取成功: {request_id}")
            else:
                await self.发送音量响应(request_id, False, None, result.get("error", "获取音量失败"))
                logger.error(f"音量获取失败: {request_id}")
        except Exception as e:
            logger.error(f"处理音量获取请求时出错: {e}", exc_info=True)
            await self.发送音量响应(request_id, False, None, str(e))

    async def _处理音量设置(self, data: Dict[str, Any]) -> None:
        """处理音量设置消息"""
        request_id = data.get("requestId", "")
        volume = data.get("volume")
        logger.info(f"收到音量设置请求: {request_id}, 音量: {volume}")
        try:
            result = await self._调用机器人服务器API("POST", "/api/v1/volume", {"volume": volume})
            if result.get("success"):
                await self.发送音量响应(request_id, True, {"message": result.get("message")})
                logger.info(f"音量设置成功: {request_id}")
            else:
                await self.发送音量响应(request_id, False, None, result.get("error", "设置音量失败"))
                logger.error(f"音量设置失败: {request_id}")
        except Exception as e:
            logger.error(f"处理音量设置请求时出错: {e}", exc_info=True)
            await self.发送音量响应(request_id, False, None, str(e))

    async def _处理设置静音(self, data: Dict[str, Any]) -> None:
        """处理设置静音消息"""
        request_id = data.get("requestId", "")
        mute = data.get("mute")
        logger.info(f"收到设置静音请求: {request_id}, 静音: {mute}")
        try:
            result = await self._调用机器人服务器API("POST", "/api/v1/volume/mute", {"mute": mute})
            if result.get("success"):
                await self.发送音量响应(request_id, True, {"message": result.get("message")})
                logger.info(f"设置静音成功: {request_id}")
            else:
                await self.发送音量响应(request_id, False, None, result.get("error", "设置静音失败"))
                logger.error(f"设置静音失败: {request_id}")
        except Exception as e:
            logger.error(f"处理设置静音请求时出错: {e}", exc_info=True)
            await self.发送音量响应(request_id, False, None, str(e))

    async def _处理配置获取(self, data: Dict[str, Any]) -> None:
        """处理配置获取消息"""
        request_id = data.get("requestId", "")
        logger.info(f"收到配置获取请求: {request_id}")
        try:
            result = await self._调用机器人服务器API("GET", "/api/v1/config")
            if result.get("success"):
                await self.发送配置响应(request_id, True, result.get("config"))
                logger.info(f"配置获取成功: {request_id}")
            else:
                await self.发送配置响应(request_id, False, None, result.get("error", "获取配置失败"))
                logger.error(f"配置获取失败: {request_id}")
        except Exception as e:
            logger.error(f"处理配置获取请求时出错: {e}", exc_info=True)
            await self.发送配置响应(request_id, False, None, str(e))

    async def _处理配置更新(self, data: Dict[str, Any]) -> None:
        """处理配置更新消息"""
        request_id = data.get("requestId", "")
        config_data = data.get("config", {})
        logger.info(f"收到配置更新请求: {request_id}")
        try:
            result = await self._调用机器人服务器API("POST", "/api/v1/config", config_data)
            if result.get("success"):
                await self.发送配置响应(request_id, True, {"message": result.get("message"), "results": result.get("results")})
                logger.info(f"配置更新成功: {request_id}")
            else:
                await self.发送配置响应(request_id, False, None, result.get("error", "更新配置失败"))
                logger.error(f"配置更新失败: {request_id}")
        except Exception as e:
            logger.error(f"处理配置更新请求时出错: {e}", exc_info=True)
            await self.发送配置响应(request_id, False, None, str(e))

    async def _处理SDK模式设置(self, data: Dict[str, Any]) -> None:
        """处理SDK模式设置消息"""
        request_id = data.get("requestId", "")
        sdk_mode = data.get("sdkMode")
        logger.info(f"收到SDK模式设置请求: {request_id}, SDK模式: {sdk_mode}")

        try:
            if sdk_mode is None:
                await self.发送SDK模式响应(request_id, False, None, "sdkMode 参数不能为空")
                return

            sdk_mode = bool(sdk_mode)

            # 如果状态没有变化，直接返回成功
            if self.sdk_mode_enabled == sdk_mode:
                logger.info(f"SDK模式已经是 {'SDK' if sdk_mode else '遥控'} 模式")
                await self.发送SDK模式响应(request_id, True, sdk_mode)
                return

            if sdk_mode:
                # 开启SDK模式：启动子程序
                logger.info("开启SDK模式，启动子程序...")
                script_dir = Path(__file__).parent
                interactive_script = script_dir / "modules" / "actions" / "executor.py"

                if not interactive_script.exists():
                    error_msg = f"找不到交互式脚本: {interactive_script}"
                    logger.error(error_msg)
                    await self.发送SDK模式响应(request_id, False, None, error_msg)
                    return

                if not self.交互式子进程控制器.启动(str(interactive_script)):
                    error_msg = "无法启动交互式子进程"
                    logger.error(error_msg)
                    await self.发送SDK模式响应(request_id, False, None, error_msg)
                    return

                self.sdk_mode_enabled = True
                logger.info("SDK模式开启成功")
                await self.发送SDK模式响应(request_id, True, True)
            else:
                # 关闭SDK模式：关闭子程序
                logger.info("关闭SDK模式，关闭子程序...")

                # 获取当前状态：检查是否是急停或趴下状态
                # 这里假设我们能通过IPC或其他方式获取到当前的动作状态
                # 如果没有跟踪机制，我们需要先执行站立动作
                # 根据需求：急停保持急停，趴下保持趴下，其他改为站立

                # TODO: 这里需要实现获取当前机器狗状态的逻辑
                # 目前简化处理：关闭前先站立
                try:
                    # 关闭前尝试让机器狗站立
                    if self.交互式子进程控制器.process and self.交互式子进程控制器.process.poll() is None:
                        logger.info("关闭子程序前，先让机器狗站立")
                        self.交互式子进程控制器.发送命令("stand_up")
                        await asyncio.sleep(2)  # 等待站立完成
                except Exception as e:
                    logger.warning(f"关闭前执行站立动作失败: {e}")

                self.交互式子进程控制器.关闭()
                self.sdk_mode_enabled = False
                logger.info("SDK模式关闭成功")
                await self.发送SDK模式响应(request_id, True, False)

        except Exception as e:
            logger.error(f"处理SDK模式设置请求时出错: {e}", exc_info=True)
            await self.发送SDK模式响应(request_id, False, None, str(e))

    async def _处理SDK模式获取(self, data: Dict[str, Any]) -> None:
        """处理SDK模式获取消息"""
        request_id = data.get("requestId", "")
        logger.info(f"收到SDK模式获取请求: {request_id}")

        try:
            await self.发送SDK模式响应(request_id, True, self.sdk_mode_enabled)
            logger.info(f"SDK模式获取成功: {request_id}, 当前模式: {'SDK' if self.sdk_mode_enabled else '遥控'}")
        except Exception as e:
            logger.error(f"处理SDK模式获取请求时出错: {e}", exc_info=True)
            await self.发送SDK模式响应(request_id, False, None, str(e))

    async def _处理日志标记(self, data: Dict[str, Any]) -> None:
        """处理日志标记消息：在本地日志中写入一个可识别标记"""
        request_id = data.get("requestId", "")
        message = data.get("message", "")
        logger.info(f"收到日志标记请求: {request_id}, 标记信息: {message}")
        try:
            result = await self._调用机器人服务器API("POST", "/api/v1/logs/mark", {"message": message})
            if result.get("success"):
                await self.发送日志标记响应(request_id, True, result.get("marker"))
                logger.info(f"日志标记写入成功: {request_id}")
            else:
                await self.发送日志标记响应(request_id, False, None, result.get("error", "写入标记失败"))
                logger.error(f"日志标记写入失败: {request_id}")
        except Exception as e:
            logger.error(f"处理日志标记请求时出错: {e}", exc_info=True)
            await self.发送日志标记响应(request_id, False, None, str(e))

    async def _处理文本响应(self, data: Dict[str, Any]) -> None:
        """ 处理文本响应消息 """
        await 处理文本响应(data, self.动作执行器, self._确保动作执行器())

    async def _处理音频控制(self, data: Dict[str, Any]) -> None:
        """ 处理音频控制消息 """
        if "enabled" in data:
            enabled = bool(data.get("enabled", True))
            self.audio_capture.audio_streaming_enabled = enabled
            logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def _处理音频响应并播放(self, data: Dict[str, Any]) -> None:
        """ 处理音频响应消息 """
        处理音频响应并播放(data)

    async def _处理停止音频播放(self, data: Dict[str, Any]) -> None:
        """ 处理停止音频播放消息 """
        停止当前音频播放()

    async def _处理动作指令(self, data: Dict[str, Any]) -> None:
        await 处理动作指令(data, self.动作执行器, self._确保动作执行器())

    async def _处理控制指令(self, data: Dict[str, Any]) -> None:
        """ 处理控制指令消息（来自云端服务器） """
        self.joystick_controller.处理命令(data)

    def _处理直连控制指令(self, data: Dict[str, Any]) -> None:
        """处理来自手机直连 WebSocket 的控制指令（同步，在 asyncio 线程安全地调用）

        command 取值：
          joystick / joystick_stop / estop → 交给摇杆控制器处理
          action                           → 通过动作执行器执行（如 stand_up）
        """
        command = data.get("command", "")
        if command in ("joystick", "joystick_stop", "estop"):
            self.joystick_controller.处理命令(data)
        elif command == "action":
            action = data.get("action", "")
            if action and self.动作执行器:
                # 在独立线程执行，避免阻塞 asyncio 事件循环
                self._确保动作执行器().submit(self.动作执行器, action, data.get("parameters", {}))
        elif command == "mic_control":
            enabled = bool(data.get("enabled", True))
            self.audio_capture.audio_streaming_enabled = enabled
            logger.info(f"[直连控制] 麦克风采集{'开启' if enabled else '关闭'}")
        elif command == "switch_control_mode":
            mode = data.get("mode", "move")
            logger.info(f"[直连控制] 控制模式切换为: {mode}")
        else:
            logger.debug(f"[直连控制] 未知指令类型: {command}")

    async def _处理直连异步命令(self, data: dict, send_fn) -> None:
        """处理来自手机直连 WebSocket 的异步指令（需要回传响应）

        command 取值：
          camera_capture → 拍照，回传 base64 图像
          sdk_mode       → 切换 SDK/遥控模式，回传结果
        """
        command = data.get("command", "")
        request_id = data.get("requestId", "direct")

        if command == "camera_capture":
            logger.info(f"[直连控制] 收到拍照请求: {request_id}")
            try:
                loop = asyncio.get_event_loop()
                rtsp_url = "rtsp://127.0.0.1:8554/test"
                image_base64 = await loop.run_in_executor(
                    None, capture_photo, rtsp_url, 5
                )
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

        elif command == "sdk_mode":
            enabled = data.get("enabled")
            logger.info(f"[直连控制] SDK 模式切换请求: {enabled}")
            try:
                if enabled is None:
                    await send_fn({"type": "sdk_mode_response", "data": {"requestId": request_id, "success": False, "error": "enabled 参数不能为空"}})
                    return
                enabled = bool(enabled)
                if self.sdk_mode_enabled == enabled:
                    await send_fn({"type": "sdk_mode_response", "data": {"requestId": request_id, "success": True, "sdkMode": enabled}})
                    return
                if enabled:
                    from pathlib import Path
                    script_dir = Path(__file__).parent
                    interactive_script = script_dir / "modules" / "actions" / "executor.py"
                    if not interactive_script.exists():
                        raise FileNotFoundError(f"找不到交互式脚本: {interactive_script}")
                    if not self.交互式子进程控制器.启动(str(interactive_script)):
                        raise RuntimeError("无法启动交互式子进程")
                    self.sdk_mode_enabled = True
                else:
                    try:
                        if self.交互式子进程控制器.process and self.交互式子进程控制器.process.poll() is None:
                            self.交互式子进程控制器.发送命令("stand_up")
                            await asyncio.sleep(2)
                    except Exception as ex:
                        logger.warning(f"[直连控制] 关闭 SDK 前执行站立失败: {ex}")
                    self.交互式子进程控制器.关闭()
                    self.sdk_mode_enabled = False
                await send_fn({"type": "sdk_mode_response", "data": {"requestId": request_id, "success": True, "sdkMode": enabled}})
                logger.info(f"[直连控制] SDK 模式已切换为: {'SDK' if enabled else '遥控'}")
            except Exception as e:
                logger.error(f"[直连控制] SDK 模式切换失败: {e}", exc_info=True)
                await send_fn({"type": "sdk_mode_response", "data": {"requestId": request_id, "success": False, "error": str(e)}})
        else:
            logger.debug(f"[直连控制] 未知异步指令: {command}")

    async def _处理服务器错误(self, data: Dict[str, Any]) -> None:
        """ 处理服务器错误消息 """
        code = data.get("code", "")
        message = data.get("message", "")
        logger.error(f"服务器错误: {code} - {message}")

    async def _处理音频流开始(self, data: Dict[str, Any]) -> None:
        """ 处理音频流开始消息 """
        logger.debug("音频流开始")

    async def _处理音频流数据块(self, data: Dict[str, Any]) -> None:
        """ 处理音频流数据块消息 """
        # 音频流数据块由底层处理，这里不需要额外处理
        pass

    async def _处理音频流结束(self, data: Dict[str, Any]) -> None:
        """ 处理音频流结束消息 """
        logger.debug("音频流结束")

    async def _处理收到的消息(self, message: Dict[str, Any]) -> None:
        """ 处理收到的消息 """
        msg_type = message.get("type")
        if not isinstance(msg_type, str):
            logger.warning(f"未知的消息类型: {msg_type}")
            return
        data = message.get("data", {})
        if not isinstance(data, dict):
            data = {}
        handler = self.message_handlers.get(msg_type)
        if handler:
            await handler(data)
        else:
            logger.warning(f"未知的消息类型: {msg_type}")

    async def 运行(self) -> None:
        """ 运行机器狗客户端 """
        logger.info("机器狗客户端启动")
        await self.ipc_server.启动()
        # 启动本地直连控制服务（独立运行，不受云端连接状态影响）
        direct_control_task = asyncio.create_task(self.ws_control_server.服务循环(), name="direct-control-ws")
        try:
            while True:
                try:
                    if not await self._确保与服务器连接():
                        continue
                    tasks = self._构建异步任务()

                    if not tasks:
                        await asyncio.sleep(1)
                        continue

                    # 使用 FIRST_COMPLETED 模式,任何任务完成(包括连接断开)都会快速响应
                    # 这样可以更快检测到断连并触发重连
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                    # 检查是否有任务因异常退出或主连接断开
                    should_reconnect = False
                    for task in done:
                        try:
                            if not task.cancelled():
                                exc = task.exception()
                                if exc:
                                    logger.warning(f"子任务异常退出: {exc}")
                                    should_reconnect = True
                        except Exception as e:
                            logger.warning(f"子任务退出: {e}")
                            should_reconnect = True

                    # 只有主连接（business）断开才需要完全重连
                    if not self.ws_manager.connected:
                        should_reconnect = True
                        logger.info("主连接已断开，准备重连...")

                    if should_reconnect:
                        # 取消剩余任务
                        for task in pending:
                            task.cancel()

                        # 等待剩余任务取消完成
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)

                        logger.info("任务组结束，准备重连...")
                    else:
                        # 某个任务正常结束(非异常),可能是次要通道断开
                        # 取消其他任务后重新构建任务组
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        logger.debug("部分任务结束，重建任务组")

                except KeyboardInterrupt:
                    logger.info("收到中断信号，正在退出...")
                    break
                except Exception as e:
                    logger.error(f"运行时错误: {e}")
                    self.ws_manager.connected = False
                finally:
                    if self._是否有活跃的WebSocket连接():
                        await self.断开连接到服务器(shutdown_resources=False)
        except asyncio.CancelledError:
            logger.info("收到中断信号，正在退出...")
        finally:
            direct_control_task.cancel()
            try:
                await direct_control_task
            except (asyncio.CancelledError, Exception):
                pass
            await self.断开连接到服务器(shutdown_resources=True)
            await self.ipc_server.关闭()
            try:
                await self.取消初始化()
            except Exception:
                pass
            logger.info("客户端已关闭")

    async def _确保与服务器连接(self) -> bool:
        """ 确保与服务器连接 """
        if self.ws_manager.connected:
            # 连接正常，重置重连间隔
            self.current_reconnect_interval = self.initial_reconnect_interval
            return True

        logger.info(f"尝试连接到服务器 (重连间隔: {self.current_reconnect_interval}秒)...")
        success = await self.连接到服务器()
        if success:
            self.current_reconnect_interval = self.initial_reconnect_interval
            logger.info("✓ 连接成功，重连间隔已重置")
            return True

        logger.warning(f"✗ 连接失败，{self.current_reconnect_interval} 秒后重试...")
        await asyncio.sleep(self.current_reconnect_interval)

        # 指数退避，最大不超过 max_reconnect_interval
        old_interval = self.current_reconnect_interval
        self.current_reconnect_interval = min(
            self.current_reconnect_interval * 2,
            self.max_reconnect_interval
        )
        if self.current_reconnect_interval != old_interval:
            logger.info(f"重连间隔已调整: {old_interval}秒 → {self.current_reconnect_interval}秒")
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
            or self.ws_manager.ws_audio_download
            or self.ws_manager.ws_audio_upload
        )

    async def 取消初始化(self) -> None:
        """ 取消初始化客户端 """
        try:
            停止当前音频播放()
        except Exception:
            pass
        try:
            # 停止配置文件监听
            self.config_store.停止监听()
            logger.info("配置文件监听已停止")
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
            self.client.交互式子进程控制器.发送命令(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
            self.client.交互式子进程控制器.发送命令(
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

    def _转换距离参数到速度(self, parameters: dict) -> tuple:
        """
        将距离/步数/角度参数转换为速度和持续时间
        返回: (vx, vy, yaw_rate, duration)
        """
        import math

        vx = 0.0
        vy = 0.0
        yaw_rate = 0.0
        duration = 0.0

        # 默认速度配置（可从config读取）
        default_vx_speed = 0.2       # 前后移动速度 m/s
        default_vy_speed = 0.15      # 左右移动速度 m/s
        default_yaw_speed = 0.5      # 转向角速度 rad/s
        default_step_distance = 0.3  # 每步距离 m (其实多了，但是更符合直觉，于是保留)
        default_move_speed = 0.2     # 斜向移动的默认速度 m/s

        # 处理步数移动 - 先转换为距离
        if "steps" in parameters:
            steps = float(parameters["steps"])
            distance = steps * default_step_distance
            parameters["distance"] = distance

        # 情况1: angle + distance/steps - 斜向移动
        if "angle" in parameters and "distance" in parameters:
            angle_deg = float(parameters["angle"])
            distance = float(parameters["distance"])
            angle_rad = angle_deg * math.pi / 180.0

            # 将角度和距离转换为 vx, vy
            # angle=0 是正前方, angle=90 是左方, angle=-90 是右方
            vx = default_move_speed * math.cos(angle_rad)
            vy = default_move_speed * math.sin(angle_rad)
            duration = abs(distance) / default_move_speed

            logger.info(f"斜向移动: 角度={angle_deg}°, 距离={distance}m, vx={vx:.2f}, vy={vy:.2f}, 时长={duration:.2f}s")
            return (vx, vy, 0.0, duration)

        # 情况2: 只有 angle - 原地转向
        if "angle" in parameters:
            angle_deg = float(parameters["angle"])
            angle_rad = abs(angle_deg * math.pi / 180.0)  # 转换为弧度
            yaw_rate = default_yaw_speed if angle_deg > 0 else -default_yaw_speed
            duration = angle_rad / default_yaw_speed
            logger.info(f"原地转向: 角度={angle_deg}°, 时长={duration:.2f}s")
            return (0.0, 0.0, yaw_rate, duration)

        # 情况3: distance + direction - 指定方向移动
        if "distance" in parameters:
            distance = float(parameters["distance"])
            direction = parameters.get("direction", "forward")

            if direction == "forward":
                vx = default_vx_speed
                duration = abs(distance) / default_vx_speed
            elif direction == "backward":
                vx = -default_vx_speed
                duration = abs(distance) / default_vx_speed
            elif direction == "left":
                vy = default_vy_speed
                duration = abs(distance) / default_vy_speed
            elif direction == "right":
                vy = -default_vy_speed
                duration = abs(distance) / default_vy_speed
            else:
                # 默认前后移动
                vx = default_vx_speed if distance > 0 else -default_vx_speed
                duration = abs(distance) / default_vx_speed

            logger.info(f"方向移动: {direction}, 距离={distance}m, 时长={duration:.2f}s")

        return (vx, vy, yaw_rate, duration)

    def 执行动作(self, action: str, parameters: dict) -> bool:
        """ 执行动作(操作机器人行动的动作) """
        try:
            token = self._下一个_token()
            logger.debug(f"开始执行动作: {action}, 参数: {parameters}")
            self._停止当前动作()
            # 特殊处理move动作
            if action == "move":
                # 检查是否使用距离/步数/角度参数
                if "distance" in parameters or "steps" in parameters or "angle" in parameters:
                    # 转换为速度+时间模式
                    vx, vy, yaw_rate, duration = self._转换距离参数到速度(parameters)
                    command = json.dumps({
                        "type": "ai_move",
                        "vx": vx,
                        "vy": vy,
                        "yaw_rate": yaw_rate,
                        "duration": duration,
                    })
                    wait_time = duration
                    logger.info(f"移动控制 (距离模式): vx={vx:.2f}, vy={vy:.2f}, yaw_rate={yaw_rate:.2f}, duration={duration:.2f}秒")
                else:
                    # 使用原有的速度模式
                    vx = parameters.get("vx", 0)
                    vy = parameters.get("vy", 0)
                    yaw_rate = parameters.get("yaw_rate", 0)
                    duration = parameters.get("duration", 2)
                    command = json.dumps({
                        "type": "ai_move",
                        "vx": vx,
                        "vy": vy,
                        "yaw_rate": yaw_rate,
                        "duration": duration,
                    })
                    wait_time = float(duration)
                    logger.info(f"移动控制 (速度模式): vx={vx}, vy={vy}, yaw_rate={yaw_rate}, duration={duration}秒")
            else:
                # 其他动作的处理
                command = action
                wait_time = self._解析等待时间(action)
            if not command:
                logger.warning(f"不支持的动作: {action}")
                return False
            success = self.client.交互式子进程控制器.发送命令(command)
            if not success:
                logger.error(f"发送命令 {command} 失败")
                return False
            completed = self._可中断的睡眠(token, wait_time)
            if not completed:
                logger.info(f"动作 {action} 被打断")
                return False
            logger.debug(f"动作 {action} 执行完成")
            return True
        except Exception as e:
            logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False

async def main():
    """主函数"""
    client = RobotClient()

    # get modules/actions/executor.py 的路径
    script_dir = Path(__file__).parent
    interactive_script = script_dir / "modules" / "actions" / "executor.py"

    if not interactive_script.exists():
        logger.error(f"找不到交互式脚本: {interactive_script}")
        return

    # 启动交互式子进程
    if not client.交互式子进程控制器.启动(str(interactive_script)):
        logger.error("无法启动交互式子进程")
        return

    client.动作执行器 = 动作执行器(client).执行动作

    # 运行客户端
    try:
        await client.运行()
    except KeyboardInterrupt:
        logger.info("客户端已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
