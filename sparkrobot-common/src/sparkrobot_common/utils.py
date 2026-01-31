"""
通用工具函数
"""
import socket
import subprocess
from pathlib import Path


def generate_uuid() -> str:
    """生成 UUID7"""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        import uuid
        return str(uuid.uuid4())  # fallback to uuid4


def generate_robot_name(uuid_val: str) -> str:
    """生成机器人名称"""
    return f"机器狗-{uuid_val[:4]}"


def get_ipc_path(org_name: str, name: str) -> Path:
    """获取 IPC socket 路径"""
    ipc_path = Path("/tmp") / org_name / f"{name}.sock"
    ipc_path.parent.mkdir(parents=True, exist_ok=True)
    return ipc_path


def get_local_ip() -> str | None:
    """通过 UDP 连接获取本机对外的 IP 地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的建立连接，仅用于获取本机出口 IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = None
    finally:
        s.close()
    return ip


def detect_robot_version() -> str | None:
    """检测机器人运控版本"""
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
    "generate_uuid",
    "generate_robot_name",
    "get_ipc_path",
    "get_local_ip",
    "detect_robot_version",
]
