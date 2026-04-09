from typing import Any

from src.core.state import (
    任务状态,
    健康状态,
    定位状态,
    导航状态,
    建图状态,
    机器人状态存储,
    激光雷达状态,
    运控桥状态,
)


class 运行时状态服务:
    """对外提供运行时状态初始化与摘要构建。"""

    def __init__(self, 状态存储: 机器人状态存储) -> None:
        self.状态存储 = 状态存储

    def 根据配置初始化(self, config: dict[str, Any]) -> None:
        """根据配置初始化状态。"""
        lidar_cfg = config.get("lidar", {})
        mapping_cfg = config.get("mapping", {})
        localization_cfg = config.get("localization", {})
        navigation_cfg = config.get("navigation", {})

        self.状态存储.更新健康状态(
            健康状态(
                在线=False,
                SDK模式=bool(config.get("sdk", {}).get("enable_sdk_on_startup", True)),
                控制模式="runtime",
                运动模式="idle",
            )
        )
        self.状态存储.更新运控桥状态(
            运控桥状态(
                在线=False,
                运动控制启用=bool(config.get("sdk", {}).get("enable_sdk_on_startup", True)),
                SDK就绪=False,
                遥测在线=False,
                允许运动=False,
                急停=False,
                裁决原因="unknown",
            )
        )
        self.状态存储.更新激光雷达状态(
            激光雷达状态(
                启用=bool(lidar_cfg.get("enabled", False)),
                已连接=False,
                传输方式=str(lidar_cfg.get("transport", "ethernet")),
                坐标系=str(lidar_cfg.get("frame_id", "laser")),
                扫描正常=False,
            )
        )
        self.状态存储.更新建图状态(
            建图状态(
                状态="disabled" if not mapping_cfg.get("enabled", False) else "idle",
                当前地图="",
                最近地图=None,
                保存目录=str(mapping_cfg.get("map_save_dir", "")),
                自动保存=bool(mapping_cfg.get("auto_save_on_stop", True)),
            )
        )
        self.状态存储.更新定位状态(
            定位状态(
                状态="disabled" if not localization_cfg.get("enabled", False) else "idle",
                地图名称=str(localization_cfg.get("default_map", "")),
                置信度=None,
            )
        )
        self.状态存储.更新导航状态(
            导航状态(
                状态="disabled" if not navigation_cfg.get("enabled", False) else "idle",
                当前目标=None,
                剩余距离=None,
                失败原因=None,
            )
        )
        self.状态存储.更新任务状态(
            任务状态(
                状态="idle",
                任务类型=None,
                任务ID=None,
            )
        )

    def 构建摘要(self) -> dict[str, Any]:
        """构建用于日志和对外暴露的状态摘要。"""
        snapshot = self.状态存储.获取快照()
        return {
            "health": {
                "online": snapshot.健康.在线,
                "battery": snapshot.健康.电量,
                "sdk_mode": snapshot.健康.SDK模式,
                "control_mode": snapshot.健康.控制模式,
                "motion_mode": snapshot.健康.运动模式,
            },
            "dog_bridge": {
                "online": snapshot.运控桥.在线,
                "motion_control_enabled": snapshot.运控桥.运动控制启用,
                "sdk_ready": snapshot.运控桥.SDK就绪,
                "telemetry_online": snapshot.运控桥.遥测在线,
                "motion_ready": snapshot.运控桥.允许运动,
                "emergency_stop": snapshot.运控桥.急停,
                "arbitration_reason": snapshot.运控桥.裁决原因,
                "command_age_sec": snapshot.运控桥.指令延迟秒,
                "telemetry_age_sec": snapshot.运控桥.遥测延迟秒,
                "target_velocity": snapshot.运控桥.目标速度,
                "output_velocity": snapshot.运控桥.输出速度,
            },
            "lidar": {
                "enabled": snapshot.激光雷达.启用,
                "connected": snapshot.激光雷达.已连接,
                "transport": snapshot.激光雷达.传输方式,
                "frame_id": snapshot.激光雷达.坐标系,
                "scan_ok": snapshot.激光雷达.扫描正常,
            },
            "mapping": {
                "state": snapshot.建图.状态,
                "current_map": snapshot.建图.当前地图,
                "last_map": snapshot.建图.最近地图,
                "save_dir": snapshot.建图.保存目录,
                "auto_save": snapshot.建图.自动保存,
            },
            "localization": {
                "state": snapshot.定位.状态,
                "map_name": snapshot.定位.地图名称,
                "confidence": snapshot.定位.置信度,
            },
            "navigation": {
                "state": snapshot.导航.状态,
                "current_goal": snapshot.导航.当前目标,
                "remaining_distance": snapshot.导航.剩余距离,
                "failure_reason": snapshot.导航.失败原因,
            },
            "task": {
                "state": snapshot.任务.状态,
                "task_type": snapshot.任务.任务类型,
                "task_id": snapshot.任务.任务ID,
            },
        }

    def 获取完整状态(self) -> dict[str, Any]:
        """获取完整状态快照。"""
        return self.状态存储.获取快照().导出字典()
