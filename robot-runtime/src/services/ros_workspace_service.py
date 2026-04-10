from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sparkrobot_common import CONFIG_DIR


@dataclass(frozen=True)
class ROS启动计划:
    """ROS2 启动计划。"""

    名称: str
    包名: str
    启动文件: str
    参数: dict[str, str]
    工作空间目录: str
    安装环境脚本: str
    命令: str

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "name": self.名称,
            "package": self.包名,
            "launch_file": self.启动文件,
            "args": dict(self.参数),
            "workspace_dir": self.工作空间目录,
            "setup_bash": self.安装环境脚本,
            "command": self.命令,
        }


class ROS工作空间服务:
    """负责发现 robot-ros 工作空间并生成启动计划。"""

    def __init__(self, config: dict[str, Any], runtime_project_dir: Path) -> None:
        self._config = config
        self.runtime_project_dir = runtime_project_dir.resolve()
        self.robot_onboard_dir = self.runtime_project_dir.parent
        self.workspace_dir = self._解析工作空间目录()
        self.src_dir = self.workspace_dir / "src"
        self.install_dir = self.workspace_dir / "install"
        self.install_setup = self.install_dir / "setup.bash"
        self.bringup_dir = self.src_dir / "sparkrobot_bringup"
        self.bringup_launch_dir = self.bringup_dir / "launch"
        self.bringup_config_dir = self.bringup_dir / "config"
        self.nav_bridge_dir = self.src_dir / "sparkrobot_nav_bridge"
        self.dog_bridge_dir = self.src_dir / "sparkrobot_dog_bridge"
        self.vendor_driver_dir = self.src_dir / "lslidar_driver"
        self.vendor_msgs_dir = self.src_dir / "lslidar_msgs"
        self.generated_config_dir = CONFIG_DIR / "generated" / "ros"

    def 获取工作空间摘要(self) -> dict[str, Any]:
        """返回 ROS 工作空间摘要。"""
        lidar_driver_config = self._构建雷达驱动参数()
        lidar_params_file = self._获取雷达参数文件(lidar_driver_config)
        plans = {name: plan.导出字典() for name, plan in self.获取启动计划().items()}
        missing_items: list[str] = []

        if not self.workspace_dir.exists():
            missing_items.append("缺少 robot-ros 工作空间目录")
        if not self.bringup_dir.exists():
            missing_items.append("缺少 sparkrobot_bringup 包")
        if not self.nav_bridge_dir.exists():
            missing_items.append("缺少 sparkrobot_nav_bridge 包")
        if not self.dog_bridge_dir.exists():
            missing_items.append("缺少 sparkrobot_dog_bridge 包")
        if not (self.vendor_driver_dir / "package.xml").exists():
            missing_items.append("缺少厂商 lslidar_driver 包，可运行导入脚本补齐")
        if not (self.vendor_msgs_dir / "package.xml").exists():
            missing_items.append("缺少厂商 lslidar_msgs 包，可运行导入脚本补齐")
        if not self.install_setup.exists():
            missing_items.append("缺少 install/setup.bash，可先在 robot-ros 下执行 colcon build")

        return {
            "workspace_dir": str(self.workspace_dir),
            "src_dir": str(self.src_dir),
            "install_setup": str(self.install_setup),
            "workspace_exists": self.workspace_dir.exists(),
            "bringup_ready": self.bringup_dir.exists(),
            "nav_bridge_ready": self.nav_bridge_dir.exists(),
            "dog_bridge_ready": self.dog_bridge_dir.exists(),
            "vendor_driver_ready": (self.vendor_driver_dir / "package.xml").exists(),
            "vendor_msgs_ready": (self.vendor_msgs_dir / "package.xml").exists(),
            "install_setup_ready": self.install_setup.exists(),
            "transport": self._获取雷达传输方式(),
            "lidar_params_file": str(lidar_params_file),
            "lidar_driver_config": lidar_driver_config,
            "default_map": self._解析默认地图路径(),
            "missing_items": missing_items,
            "plans": plans,
        }

    def 获取启动计划(self) -> dict[str, ROS启动计划]:
        """返回常用启动计划。"""
        return {
            name: self.获取启动计划项(name)
            for name in self._获取启动计划规格()
        }

    def 获取启动计划项(self, 名称: str, 额外参数: dict[str, str] | None = None) -> ROS启动计划:
        """获取单个启动计划，并允许在调用时覆写部分参数。"""
        规格 = self._获取启动计划规格().get(名称)
        if 规格 is None:
            raise KeyError(f"未定义的 ROS 启动计划: {名称}")

        包名, 启动文件, 默认参数 = 规格
        参数 = dict(默认参数)
        if 额外参数:
            参数.update({key: value for key, value in 额外参数.items() if value})

        return self._构建启动计划(
            名称=名称,
            包名=包名,
            启动文件=启动文件,
            参数=参数,
        )

    def _获取启动计划规格(self) -> dict[str, tuple[str, str, dict[str, str]]]:
        """返回启动计划规格。"""
        return {
            "bringup": (
                "sparkrobot_bringup",
                "bringup.launch.py",
                {
                    "lidar_params": str(self._获取雷达参数文件()),
                    "base_frame": self._获取坐标系("base_frame", "base_link"),
                    "laser_frame": self._获取激光坐标系(),
                },
            ),
            "mapping": (
                "sparkrobot_bringup",
                "mapping.launch.py",
                {
                    "slam_params_file": str(self.bringup_config_dir / "slam_toolbox_online_async.yaml"),
                },
            ),
            "localization": (
                "sparkrobot_bringup",
                "localization.launch.py",
                {
                    "params_file": str(self.bringup_config_dir / "nav2.yaml"),
                    "map": self._解析默认地图路径(),
                },
            ),
            "navigation": (
                "sparkrobot_bringup",
                "navigation.launch.py",
                {
                    "params_file": str(self.bringup_config_dir / "nav2.yaml"),
                },
            ),
        }

    def _构建启动计划(
        self,
        名称: str,
        包名: str,
        启动文件: str,
        参数: dict[str, str],
    ) -> ROS启动计划:
        filtered_args = {key: value for key, value in 参数.items() if value}
        ros_command_parts = ["ros2", "launch", 包名, 启动文件]
        ros_command_parts.extend(f"{key}:={value}" for key, value in filtered_args.items())
        ros_command = " ".join(shlex.quote(part) for part in ros_command_parts)
        bash_script = f"source {shlex.quote(str(self.install_setup))} && {ros_command}"
        command = f"bash -lc {shlex.quote(bash_script)}"
        return ROS启动计划(
            名称=名称,
            包名=包名,
            启动文件=启动文件,
            参数=filtered_args,
            工作空间目录=str(self.workspace_dir),
            安装环境脚本=str(self.install_setup),
            命令=command,
        )

    def _解析工作空间目录(self) -> Path:
        configured = self._读取可选字符串("ros", "workspace_dir")
        if configured:
            return Path(configured).expanduser()
        return self.robot_onboard_dir / "robot-ros"

    def _获取雷达参数文件(self, driver_config: dict[str, str | int | float | bool] | None = None) -> Path:
        if driver_config is None:
            driver_config = self._构建雷达驱动参数()

        transport = self._获取雷达传输方式()
        filename = f"lidar_runtime_{transport}.yaml"
        target_path = self.generated_config_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self._渲染雷达参数文件(driver_config), encoding="utf-8")
        return target_path

    def _获取雷达传输方式(self) -> str:
        raw_value = self._读取可选字符串("lidar", "transport")
        if raw_value and raw_value.lower() == "serial":
            return "serial"
        return "ethernet"

    def _构建雷达驱动参数(self) -> dict[str, str | int | float | bool]:
        transport = self._获取雷达传输方式()
        host_ip = self._读取可选字符串("lidar", "host_ip") or "192.168.1.102"

        return {
            "frame_id": self._获取激光坐标系(),
            "group_ip": "224.1.1.2",
            "add_multicast": False,
            "device_ip": self._读取可选字符串("lidar", "device_ip") or "192.168.1.200",
            "device_ip_difop": host_ip,
            "msop_port": self._读取整数("lidar", "msop_port", 2368),
            "difop_port": self._读取整数("lidar", "difop_port", 2369),
            "lidar_name": self._获取雷达型号(),
            "angle_disable_min": self._读取浮点数("lidar", "angle_disable_min", 0.0),
            "angle_disable_max": self._读取浮点数("lidar", "angle_disable_max", 0.0),
            "min_range": self._读取浮点数("lidar", "min_range", 0.2),
            "max_range": self._读取浮点数("lidar", "max_range", 25.0),
            "use_gps_ts": False,
            "scan_topic": "/scan",
            "interface_selection": "serial" if transport == "serial" else "net",
            "serial_port_": self._读取可选字符串("lidar", "serial_port") or "/dev/wheeltec_laser",
            "high_reflection": False,
            "compensation": False,
            "pubScan": True,
            "pubPointCloud2": False,
            "pointcloud_topic": "/lslidar_point_cloud",
        }

    def _渲染雷达参数文件(self, driver_config: dict[str, str | int | float | bool]) -> str:
        lines = [
            "/lslidar_driver_node:",
            "  ros__parameters:",
        ]
        for key, value in driver_config.items():
            lines.append(f"    {key}: {self._格式化YAML值(value)}")
        lines.append("")
        return "\n".join(lines)

    def _格式化YAML值(self, value: str | int | float | bool) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        return str(value)

    def _获取雷达型号(self) -> str:
        raw_value = self._读取可选字符串("lidar", "device_model")
        if not raw_value:
            return "N10_P"

        normalized = raw_value.strip().lower().replace("-", "").replace("_", "")
        model_mapping = {
            "n10": "N10",
            "n10p": "N10_P",
            "l10": "L10",
            "m10": "M10",
            "m10p": "M10_P",
            "m10plus": "M10_PLUS",
            "m10double": "M10_DOUBLE",
            "m10gps": "M10_GPS",
        }
        return model_mapping.get(normalized, raw_value.strip())

    def _解析默认地图路径(self) -> str:
        raw_map = self._读取可选字符串("localization", "default_map")
        if not raw_map:
            return ""

        map_path = Path(raw_map).expanduser()
        if map_path.is_absolute():
            return str(map_path)

        mapping_dir = self._获取地图目录()
        if map_path.suffix:
            return str(mapping_dir / map_path)
        return str(mapping_dir / f"{raw_map}.yaml")

    def _获取地图目录(self) -> Path:
        configured = self._读取可选字符串("mapping", "map_save_dir")
        if configured:
            return Path(configured).expanduser()
        return self.robot_onboard_dir / "maps"

    def _获取激光坐标系(self) -> str:
        laser_frame = self._读取可选字符串("frames", "laser_frame")
        if laser_frame:
            return laser_frame

        lidar_frame = self._读取可选字符串("lidar", "frame_id")
        if lidar_frame:
            return lidar_frame
        return "laser"

    def _获取坐标系(self, key: str, fallback: str) -> str:
        value = self._读取可选字符串("frames", key)
        if value:
            return value
        return fallback

    def _读取整数(self, section: str, key: str, fallback: int) -> int:
        value = self._读取可选值(section, key)
        if isinstance(value, bool) or value is None:
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _读取浮点数(self, section: str, key: str, fallback: float) -> float:
        value = self._读取可选值(section, key)
        if isinstance(value, bool) or value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _读取可选值(self, section: str, key: str) -> Any | None:
        section_value = self._config.get(section, {})
        if not isinstance(section_value, dict):
            return None
        return section_value.get(key)

    def _读取可选字符串(self, section: str, key: str) -> str | None:
        value = self._读取可选值(section, key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


__all__ = ["ROS启动计划", "ROS工作空间服务"]
