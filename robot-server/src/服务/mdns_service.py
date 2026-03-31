"""
mDNS 服务模块 - 在局域网广播机器人服务

使用 zeroconf 库实现 mDNS 服务注册，允许 phone-app 自动发现机器人。
"""
import socket
import subprocess
import threading
from typing import TYPE_CHECKING

from sparkrobot_common import get_logger
from sparkrobot_common.utils import 获取本机IP
from zeroconf import ServiceInfo, Zeroconf

if TYPE_CHECKING:
    from .config_service import ConfigManager

SERVICE_TYPE = "_sparkrobot._tcp.local."
logger = get_logger("robot-server")


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
        self._last_ip: str | None = None
        self._stop_event = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._service_properties: dict[str, str] | None = None
        self._monitor_process: subprocess.Popen[str] | None = None

    def _获取机器人信息(self) -> dict[str, str]:
        """从配置中获取机器人信息"""
        config = self.config_manager.获取()
        robot_config = config.get("robot", {})

        return {
            "uuid": robot_config.get("uuid", ""),
            "name": robot_config.get("name", ""),
            "model": robot_config.get("model", "agibot-d1"),
            "version": robot_config.get("agent_version", "0.0.0"),
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
                logger.warning("[mDNS] 机器人 UUID 为空，无法启动 mDNS 服务")
                return False

            local_ip = 获取本机IP()

            service_name = f"sparkrobot-{robot_uuid[:8]}.{SERVICE_TYPE}"

            properties = {
                "uuid": robot_uuid,
                "name": robot_info["name"] or f"机器狗-{robot_uuid[:4]}",
                "model": robot_info["model"],
                "version": robot_info["version"], # 机器人版本信息（robot-agent版本）
                "ip": local_ip,
                "port": str(self.port),
            }
            self._service_properties = properties

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
            self._last_ip = local_ip
            self._启动监听()

            logger.info( "[mDNS] 服务已启动")
            logger.info(f"       服务名称: {service_name}")
            logger.info(f"       IP: {local_ip}:{self.port}")
            logger.info(f"       UUID: {robot_uuid}")
            logger.info(f"       名称: {properties['name']}")

            return True

        except Exception as e:
            logger.error(f"[mDNS] 启动失败: {e}", exc_info=True)
            return False

    def _启动监听(self) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._监听IP变化, daemon=True)
        self._watch_thread.start()

    def _监听IP变化(self) -> None:
        try:
            self._monitor_process = subprocess.Popen(
                ["ip", "monitor", "addr"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            logger.error(f"[mDNS] 监听启动失败: {e}", exc_info=True)
            return
        if not self._monitor_process.stdout:
            return
        while not self._stop_event.is_set():
            line = self._monitor_process.stdout.readline()
            if not line:
                if self._monitor_process.poll() is not None:
                    break
                continue
            if "wlan0" not in line and "ap0" not in line:
                continue
            current_ip = 获取本机IP()
            if current_ip != self._last_ip and current_ip != "127.0.0.1":
                self._更新IP(current_ip)
                self._last_ip = current_ip

    def _更新IP(self, ip: str) -> None:
        if not self.zeroconf or not self.service_info or not self._service_properties:
            return
        try:
            self._service_properties["ip"] = ip
            updated_info = ServiceInfo(
                type_=self.service_info.type,
                name=self.service_info.name,
                port=self.service_info.port,
                properties=self._service_properties,
                server=self.service_info.server,
                addresses=[socket.inet_aton(ip)],
            )
            self.zeroconf.update_service(updated_info)
            self.service_info = updated_info
            logger.info(f"[mDNS] IP 已更新: {ip}:{self.port}")
        except Exception as e:
            logger.error(f"[mDNS] 更新 IP 失败: {e}", exc_info=True)

    def 停止(self) -> None:
        """停止 mDNS 服务广播"""
        try:
            self._stop_event.set()
            if self._monitor_process and self._monitor_process.poll() is None:
                self._monitor_process.terminate()
                try:
                    self._monitor_process.wait(timeout=2)
                except Exception:
                    self._monitor_process.kill()
            if self._watch_thread and self._watch_thread.is_alive():
                self._watch_thread.join(timeout=2)
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                logger.info("[mDNS] 服务已停止")
        except Exception as e:
            logger.error(f"[mDNS] 停止时出错: {e}", exc_info=True)
        finally:
            self.zeroconf = None
            self.service_info = None
            self._watch_thread = None
            self._last_ip = None
            self._service_properties = None
            self._monitor_process = None

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
