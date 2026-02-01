"""
mDNS 服务模块 - 在局域网广播机器人服务

使用 zeroconf 库实现 mDNS 服务注册，允许 robot-cloud 自动发现机器人。
"""
import socket
from typing import TYPE_CHECKING

from sparkrobot_common.utils import 获取本机IP
from zeroconf import ServiceInfo, Zeroconf

if TYPE_CHECKING:
    from .config_service import ConfigManager

SERVICE_TYPE = "_sparkrobot._tcp.local."


class MDNSService:
    """mDNS 服务管理器"""

    def __init__(self, config_manager: "ConfigManager", port: int = 8080):
        """
        初始化 mDNS 服务

        Args:
            config_manager: 配置管理器实例，用于获取机器人信息
            port: HTTP 服务端口
        """
        self.config_manager = config_manager
        self.port = port
        self.zeroconf: Zeroconf | None = None
        self.service_info: ServiceInfo | None = None

    def _获取机器人信息(self) -> dict[str, str]:
        """从配置中获取机器人信息"""
        config = self.config_manager.获取()
        robot_config = config.get("robot", {})

        return {
            "uuid": robot_config.get("uuid", ""),
            "name": robot_config.get("name", ""),
            "model": robot_config.get("model", "agibot-d1"),
            "version": robot_config.get("version", "0.0.0"),
        }

    def 启动(self) -> bool:
        """
        启动 mDNS 服务广播

        Returns:
            是否成功启动
        """
        try:
            robot_info = self._获取机器人信息()
            robot_uuid = robot_info["uuid"]

            if not robot_uuid:
                print("[mDNS] 警告: 机器人 UUID 为空，无法启动 mDNS 服务")
                return False

            local_ip = 获取本机IP()

            service_name = f"sparkrobot-{robot_uuid[:8]}.{SERVICE_TYPE}"

            properties = {
                "uuid": robot_uuid,
                "name": robot_info["name"] or f"机器狗-{robot_uuid[:4]}",
                "model": robot_info["model"],
                "version": robot_info["version"],
                "ip": local_ip,
                "port": str(self.port),
            }

            self.service_info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=service_name,
                port=self.port,
                properties=properties,
                server=f"sparkrobot-{robot_uuid[:8]}.local.",
                addresses=[socket.inet_aton(local_ip)],
            )

            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info)

            print("[mDNS] 服务已启动:")
            print(f"       服务名称: {service_name}")
            print(f"       IP: {local_ip}:{self.port}")
            print(f"       UUID: {robot_uuid}")
            print(f"       名称: {properties['name']}")

            return True

        except Exception as e:
            print(f"[mDNS] 启动失败: {e}")
            return False

    def 停止(self) -> None:
        """停止 mDNS 服务广播"""
        try:
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                print("[mDNS] 服务已停止")
        except Exception as e:
            print(f"[mDNS] 停止时出错: {e}")
        finally:
            self.zeroconf = None
            self.service_info = None

    def 更新(self) -> None:
        """更新 mDNS 服务信息（配置变更时调用）"""
        if self.zeroconf and self.service_info:
            self.停止()
            self.启动()


_mdns_service: MDNSService | None = None


def 获取_mDNS_服务单例() -> MDNSService | None:
    """获取全局 mDNS 服务实例"""
    return _mdns_service


def 初始化并启动_mDNS_服务(config_manager: "ConfigManager", port: int = 8080) -> MDNSService:
    """
    初始化并启动 mDNS 服务

    Args:
        config_manager: 配置管理器
        port: 服务端口

    Returns:
        MDNSService 实例
    """
    global _mdns_service
    _mdns_service = MDNSService(config_manager, port)
    _mdns_service.启动()
    return _mdns_service
