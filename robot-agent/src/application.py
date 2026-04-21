"""
机器狗客户端
功能:
- 配置管理（~/sparkrobot/config/config.toml）
- 配置热更新（watchdog 监听）
- WebSocket 通信（云端服务器）
- 云端 MediaMTX 正式视频推流
- 本地直连 WebSocket 控制服务（端口 8082，手机同局域网时直接发送指令，无需经过云端）
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- HTTP API服务（拍照等功能）
- 日志记录
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from sparkrobot_common import WORKSPACE_DIR, configure_logger, get_logger, 检测机器人运控版本

from src.core.config import Config
from src.core.robot_server_client import RobotServerClient
from src.modules.actions.runtime import 动作执行器, 动作调度器
from src.modules.audio.capture import AudioCapture
from src.modules.audio.playback import 停止当前音频播放
from src.modules.control.direct_control_handler import 直连控制处理器
from src.modules.control.ipc import IpcServer
from src.modules.control.joystick import JoystickController
from src.modules.control.process import ProcessController
from src.modules.control.sdk_mode_manager import SDK模式管理器
from src.modules.control.ws_control_server import WsControlServer
from src.modules.runtime import 客户端运行时协调器, 本地运行时客户端
from src.modules.transport.business_message_handler import 业务消息处理器
from src.modules.transport.message_sender import 消息发送器
from src.modules.transport.ws_manager import WebSocketManager
from src.modules.vision.cloud_media import 云端媒体推流管理器

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
        self.config = self.config_store.获取()

        # 设置日志
        self._初始化日志()

        # 启动配置文件监听（热更新）
        if self.config_store.启动监听():
            logger.info("配置文件监听已启动")
            self.config_store.注册配置变更回调(self._处理配置变化)
        else:
            logger.warning("配置文件监听启动失败，热更新功能不可用")

        self.ws_manager = WebSocketManager(self.config)
        self.message_sender = 消息发送器(self.ws_manager, self._获取当前配置, self._获取注册版本信息)
        self.robot_server_client = RobotServerClient()
        self.交互式子进程控制器 = ProcessController()
        self.joystick_controller = JoystickController(self.交互式子进程控制器)
        self._action_executor = ThreadPoolExecutor(max_workers=4)
        self.audio_task: Optional[asyncio.Task] = None
        self._ipc_status_task: Optional[asyncio.Task] = None
        self._media_stream_task: Optional[asyncio.Task] = None
        self._ipc_status_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._云端媒体推流租约到期时间 = 0.0

        """ 初始化音频捕获 """
        self.audio_capture = AudioCapture(
            self.config,
            is_connected=lambda: self.ws_manager.connected,
            is_upload_connected=lambda: self.ws_manager.connected_audio_upload,
            send_audio_start=self.message_sender.发送音频开始,
            # 如需改回原始帧上传，可在这里切换发送回调。
            send_audio_chunk=self.message_sender.发送音频数据块,
            send_audio_end=self.message_sender.发送音频结束,
        )

        """ 初始化 IPC 服务器 """
        self.ipc_server = IpcServer(self.project_name, self._处理IPC状态)
        self.media_streamer = 云端媒体推流管理器(self.config)
        self.runtime_client = 本地运行时客户端()

        """ 初始化动作执行函数 """
        self.动作执行器: Optional[Callable[[str, dict[str, Any]], bool]] = None
        self.动作控制器: Optional[动作执行器] = None
        self.动作调度器 = 动作调度器(self)

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
        robot_server_dir = Path(__file__).resolve().parents[2] / "robot-server"
        self._robot_server_version = self.robot_server_client.获取版本(robot_server_dir)
        self.config_store.设置("robot.server_version", self._robot_server_version)

        self.config = self.config_store.获取()
        self.sdk_mode_enabled = bool(self.config.get("sdk", {}).get("enable_sdk_on_startup", True))

        self.sdk_mode_manager = SDK模式管理器(
            交互式子进程控制器=self.交互式子进程控制器,
            动作调度器=self.动作调度器,
            获取SDK模式启用状态=lambda: self.sdk_mode_enabled,
            设置SDK模式启用状态=self._设置SDK模式启用状态,
            创建动作控制器=self._创建动作控制器,
            设置动作控制器=self.设置动作控制器,
            获取执行器脚本路径=self._获取动作执行器脚本路径,
            执行关闭前动作=self._按配置执行SDK关闭动作,
        )
        self.业务消息处理器 = 业务消息处理器(
            message_sender=self.message_sender,
            robot_server_client=self.robot_server_client,
            workspace=self.config_store.workspace,
            获取配置=self._获取当前配置,
            获取动作执行器=self._确保动作执行器,
            提交动作=self.提交动作,
            joystick_controller=self.joystick_controller,
            audio_capture=self.audio_capture,
            sdk_mode_manager=self.sdk_mode_manager,
            runtime_client=self.runtime_client,
            设置云端媒体租约到期时间=self._设置云端媒体推流租约到期时间,
        )
        self.直连控制处理器 = 直连控制处理器(
            joystick_controller=self.joystick_controller,
            audio_capture=self.audio_capture,
            提交动作=self.提交动作,
            sdk_mode_manager=self.sdk_mode_manager,
        )
        self.ws_control_server = WsControlServer(
            self.直连控制处理器.处理控制指令,
            self.直连控制处理器.处理异步命令,
        )
        self.runtime_coordinator = 客户端运行时协调器(
            ws_manager=self.ws_manager,
            ipc_server=self.ipc_server,
            ws_control_server=self.ws_control_server,
            media_streamer=self.media_streamer,
            audio_capture=self.audio_capture,
            message_sender=self.message_sender,
            处理收到的消息=self.业务消息处理器.处理收到的消息,
            连接到服务器=self.连接到服务器,
            断开连接到服务器=self.断开连接到服务器,
            取消初始化=self.取消初始化,
            允许云端媒体推流=self._允许云端媒体推流,
            runtime_client=self.runtime_client,
            获取机器人UUID=lambda: str(self.config["robot"]["uuid"]),
            获取初始重连间隔=lambda: self.config.get("cloud", {}).get("reconnect_interval", 5),
        )

    def _处理配置变化(self, new_config: Dict[str, Any]) -> None:
        """配置变更回调"""
        logger.info("检测到配置变更，正在更新...")
        self.config = new_config
        # 更新相关组件的配置
        self.ws_manager.更新配置(new_config)
        self.audio_capture.config = new_config
        self.media_streamer.更新配置(new_config)
        # 更新重连间隔
        if hasattr(self, "runtime_coordinator"):
            self.runtime_coordinator.更新初始重连间隔(self.config.get("cloud", {}).get("reconnect_interval", 5))

    def _获取当前配置(self) -> dict[str, Any]:
        """获取当前生效配置。"""
        return self.config

    def _获取注册版本信息(self) -> dict[str, str]:
        """获取注册消息所需的版本信息。"""
        return {
            "agent_version": self._agent_version,
            "motion_control_version": self._motion_control_version,
            "robot_server_version": self._robot_server_version,
        }

    def _设置SDK模式启用状态(self, enabled: bool) -> None:
        """更新当前 SDK 模式状态。"""
        self.sdk_mode_enabled = enabled

    def _获取动作执行器脚本路径(self) -> Path:
        """获取动作执行器脚本路径。"""
        script_dir = Path(__file__).parent
        return script_dir / "modules" / "actions" / "executor.py"

    def _创建动作控制器(self) -> 动作执行器:
        """创建新的动作控制器实例。"""
        return 动作执行器(self)

    def _设置云端媒体推流租约到期时间(self, expires_at: float) -> None:
        """更新云端媒体推流租约到期时间。"""
        self._云端媒体推流租约到期时间 = expires_at

    def _云端媒体是否按需推流(self) -> bool:
        """是否启用按需推流模式。"""
        media_cfg = self.config.get("media", {})
        return bool(media_cfg.get("stream_on_demand", True))

    def _当前云端媒体租约是否有效(self) -> bool:
        """当前本地保存的云端媒体租约是否仍有效。"""
        return self._云端媒体推流租约到期时间 > time.monotonic()

    def _允许云端媒体推流(self) -> bool:
        """根据连接状态和观看租约决定是否允许 ffmpeg 运行。"""
        if not self.ws_manager.connected:
            return False
        if not self._云端媒体是否按需推流():
            return True
        return self._当前云端媒体租约是否有效()


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

    async def 连接到服务器(self) -> list[str]:
        """连接所有已启用上游。"""
        robot_uuid = self.config["robot"]["uuid"]
        新连接上游 = await self.ws_manager.连接(robot_uuid)
        if 新连接上游:
            await self.message_sender.发送注册(新连接上游)
        return 新连接上游

    async def 断开连接到服务器(self, shutdown_resources: bool = False) -> None:
        """断开连接"""
        await self.ws_manager.断开连接()
        if shutdown_resources:
            await self.media_streamer.停止()
            self.交互式子进程控制器.关闭()
            if self._action_executor:
                self._action_executor.shutdown(wait=False)

    async def _处理IPC状态(self, status_msg: Dict[str, Any]) -> None:
        await self.runtime_coordinator.处理IPC状态(status_msg)

    async def _按配置执行SDK关闭动作(self, 日志前缀: str = "") -> None:
        process = self.交互式子进程控制器.process
        if not process or process.poll() is not None:
            return
        behavior = self.config.get("actions", {}).get("exit_behavior", "lie_down")
        if behavior == "stand_up":
            exit_command = "exit_stand_up"
        elif behavior == "stop":
            exit_command = "exit_stop"
        else:
            exit_command = "exit_lie_down"
        log_prefix = f"{日志前缀} " if 日志前缀 else ""
        logger.info(f"{log_prefix}关闭子程序前执行退出动作: {exit_command}")
        if not self.交互式子进程控制器.发送命令(exit_command):
            logger.warning(f"{log_prefix}关闭子程序前发送退出动作失败: {exit_command}")
            return
        await asyncio.sleep(3)

    async def 运行(self) -> None:
        """运行机器狗客户端。"""
        await self.runtime_coordinator.运行()

    def _确保动作执行器(self) -> ThreadPoolExecutor:
        if not self._action_executor or getattr(self._action_executor, "_shutdown", False):
            self._action_executor = ThreadPoolExecutor(max_workers=1)
        return self._action_executor

    async def 取消初始化(self) -> None:
        """ 取消初始化客户端 """
        self.动作调度器.关闭()
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

    def 设置动作控制器(self, action_controller: Optional[动作执行器]) -> None:
        self.动作控制器 = action_controller
        self.动作执行器 = action_controller.执行动作 if action_controller else None

    def 提交动作(self, action: str, parameters: Optional[dict] = None) -> bool:
        return self.动作调度器.提交(action, parameters or {})

async def main():
    """主函数"""
    client = RobotClient()

    # get modules/actions/executor.py 的路径
    interactive_script = client._获取动作执行器脚本路径()

    if not interactive_script.exists():
        logger.error(f"找不到交互式脚本: {interactive_script}")
        return

    # 如果启用了SDK模式，启动交互式脚本
    if client.sdk_mode_enabled:
        if not client.交互式子进程控制器.启动(str(interactive_script)):
            logger.error("无法启动交互式子进程")
            return
        client.设置动作控制器(client._创建动作控制器())

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
