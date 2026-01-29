import socket
from pathlib import Path
import subprocess
from typing import Optional
import uuid6  # python3.11才自带uuid7，需要用第三方库

from core.config import ORG_NAME
from core.logger import logger



# 生成uuid7
def generate_uuid() -> str:
    return str(uuid6.uuid7())

# 获取IPC路径
def get_ipc_path(name: str) -> Path:
    ipc_path = Path("/tmp") / ORG_NAME / f"{name}.sock"
    ipc_path.parent.mkdir(parents=True, exist_ok=True)
    return ipc_path

# 获取本地IP
def get_local_ip():
    """通过UDP连接获取本机对外的IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的建立连接，仅用于获取本机出口IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logger.error(f"获取出口IP失败: {e}")
        ip = None
    finally:
        s.close()
    return ip


def detect_robot_version() -> Optional[str]:
    """ 检测机器人运控版本 """
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

__all__ = [
    "execute_concurrently",
    "get_local_ip",
    "generate_uuid",
    "get_ipc_path",
    "detect_robot_version"
]
