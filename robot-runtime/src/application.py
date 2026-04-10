import asyncio
from pathlib import Path

from sparkrobot_common import WORKSPACE_DIR, configure_logger, get_logger

from src.core.config import 运行时配置
from src.core.ipc import 运行时IPC服务器
from src.core.state import 机器人状态存储
from src.services import ROS导航桥客户端, ROS工作空间服务, ROS进程管理服务, 运行时控制服务, 运行时状态服务

from . import __version__ as ROBOT_RUNTIME_VERSION

APP_NAME = "robot-runtime"
logger = get_logger(APP_NAME)


class 机器人运行时应用:
    """本体运行时应用。"""

    def __init__(self) -> None:
        self.workspace = WORKSPACE_DIR
        self.config = 运行时配置()
        self.log_dir = self.workspace / "logs" / APP_NAME
        self.map_dir = self._解析目录配置("mapping.map_save_dir", self.workspace / "maps")
        self.waypoint_dir = self._解析目录配置("patrol.waypoint_dir", self.workspace / "waypoints")
        self._初始化运行目录()
        self._初始化日志()

        self.状态存储 = 机器人状态存储()
        self.状态服务 = 运行时状态服务(self.状态存储)
        self.配置摘要 = self.config.获取()
        self.状态服务.根据配置初始化(self.配置摘要)
        self.ros工作空间服务 = ROS工作空间服务(self.配置摘要, Path(__file__).resolve().parent.parent)
        self.ros进程服务 = ROS进程管理服务(self.ros工作空间服务, self.log_dir / "ros")
        self.ros导航桥客户端 = ROS导航桥客户端()
        self.控制服务 = 运行时控制服务(
            self.状态存储,
            self.配置摘要,
            self.ros工作空间服务,
            self.ros进程服务,
            self.ros导航桥客户端,
        )
        self.ros进程服务.设置退出回调(self.控制服务.处理ROS进程退出)
        self.ipc_server = 运行时IPC服务器(APP_NAME, self.状态服务, self.控制服务)

    def _解析目录配置(self, key: str, fallback: Path) -> Path:
        """解析目录配置。"""
        configured = str(self.config.获取(key) or "").strip()
        if not configured:
            return fallback
        return Path(configured).expanduser()

    def _初始化运行目录(self) -> None:
        """初始化运行目录。"""
        for path in (self.log_dir, self.map_dir, self.waypoint_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _初始化日志(self) -> None:
        """初始化日志。"""
        logging_cfg = self.config.获取("logging") or {}
        level = logging_cfg.get("level", "INFO")
        max_file_size_mb = logging_cfg.get("max_file_size_mb")
        global logger
        logger = configure_logger(
            app_name=APP_NAME,
            log_dir=self.log_dir,
            level=level,
            max_file_size_mb=max_file_size_mb,
            log_file_prefix="application",
        )

    async def 运行(self) -> None:
        """运行本体运行时主循环。"""
        await self.ipc_server.启动()
        try:
            logger.info("本体运行时启动")
            logger.info("运行时版本: %s", ROBOT_RUNTIME_VERSION)
            logger.info("工作目录: %s", self.workspace)
            logger.info("地图目录: %s", self.map_dir)
            logger.info("路点目录: %s", self.waypoint_dir)

            lidar_cfg = self.config.获取("lidar") or {}
            mapping_cfg = self.config.获取("mapping") or {}
            navigation_cfg = self.config.获取("navigation") or {}
            logger.info(
                "运行时配置摘要: lidar.enabled=%s, lidar.transport=%s, mapping.enabled=%s, navigation.enabled=%s",
                lidar_cfg.get("enabled", False),
                lidar_cfg.get("transport", "ethernet"),
                mapping_cfg.get("enabled", False),
                navigation_cfg.get("enabled", False),
            )

            ros_summary = self.ros工作空间服务.获取工作空间摘要()
            logger.info(
                "ROS 工作空间摘要: workspace=%s, bringup_ready=%s, nav_bridge_ready=%s, dog_bridge_ready=%s, vendor_driver_ready=%s, install_setup_ready=%s",
                ros_summary["workspace_dir"],
                ros_summary["bringup_ready"],
                ros_summary["nav_bridge_ready"],
                ros_summary["dog_bridge_ready"],
                ros_summary["vendor_driver_ready"],
                ros_summary["install_setup_ready"],
            )
            lidar_driver_cfg = ros_summary["lidar_driver_config"]
            logger.info(
                "ROS 雷达参数摘要: transport=%s, params_file=%s, interface=%s, lidar_name=%s, frame_id=%s, serial_port=%s, device_ip=%s, host_ip=%s, msop_port=%s, difop_port=%s",
                ros_summary["transport"],
                ros_summary["lidar_params_file"],
                lidar_driver_cfg["interface_selection"],
                lidar_driver_cfg["lidar_name"],
                lidar_driver_cfg["frame_id"],
                lidar_driver_cfg["serial_port_"],
                lidar_driver_cfg["device_ip"],
                lidar_driver_cfg["device_ip_difop"],
                lidar_driver_cfg["msop_port"],
                lidar_driver_cfg["difop_port"],
            )
            for item in ros_summary["missing_items"]:
                logger.warning("ROS 工作空间未就绪: %s", item)
            for name, plan in self.ros工作空间服务.获取启动计划().items():
                logger.debug("ROS 启动计划[%s]: %s", name, plan.导出字典())

            循环计数 = 0
            while True:
                await self.控制服务.同步桥接状态()
                循环计数 += 1
                if 循环计数 >= 60:
                    summary = self.状态服务.构建摘要()
                    logger.debug("运行时状态摘要: %s", summary)
                    循环计数 = 0
                await asyncio.sleep(1)
        finally:
            await self.控制服务.关闭()
            await self.ipc_server.关闭()


async def main() -> None:
    """主函数。"""
    app = 机器人运行时应用()
    await app.运行()
