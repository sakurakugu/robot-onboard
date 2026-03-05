"""
通用工具函数
"""
import re
import socket
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path


def 生成UUID() -> str:
    """生成 UUID7"""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        import uuid
        return str(uuid.uuid7()) # type: ignore[attr-defined]


def 生成机器人名称(uuid_val: str) -> str:
    """生成机器人名称"""
    return f"机器狗-{uuid_val[:4]}"


def 获取IPC路径(org_name: str, name: str) -> Path:
    """获取 IPC socket 路径"""
    ipc_path = Path("/tmp") / org_name / f"{name}.sock"
    ipc_path.parent.mkdir(parents=True, exist_ok=True)
    return ipc_path


def _获取接口IPv4(interface: str) -> str | None:
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", interface],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        match = re.search(r"\s+inet\s+(\d+\.\d+\.\d+\.\d+)/", result.stdout)
        if not match:
            return None
        ip = match.group(1)
        if ip.startswith("127."):
            return None
        return ip
    except Exception:
        return None


def 获取本机IP() -> str:
    """获取本机对外的 IP 地址，优先 WIFI，其次 AP"""
    wlan_ip = _获取接口IPv4("wlan0")
    if wlan_ip:
        return wlan_ip
    ap_ip = _获取接口IPv4("ap0")
    if ap_ip:
        return ap_ip
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 不会真的建立连接，仅用于获取本机出口 IP
            s.connect(("8.8.8.8", 80))
            ip: str = s.getsockname()[0]
        return ip
    except Exception:
        return "127.0.0.1"


def 检测机器人运控版本() -> str | None:
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

def 获取AP的Wifi名称():
    with open("/etc/hostapd/hostapd.conf", "r") as f:
        for line in f:
            if line.startswith("ssid="):
                return line.strip().split("=", 1)[1]


def 获取项目版本(项目目录: Path, 包名: str | None = None, 默认版本: str = "0.1.0") -> str:
    """优先读取项目根目录 pyproject.toml 的版本号，失败后可回退到已安装包版本。"""
    pyproject = 项目目录 / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', content)
            if match:
                ver = match.group(1).strip()
                if ver:
                    return ver
        except Exception:
            pass

    if 包名:
        try:
            return pkg_version(包名)
        except PackageNotFoundError:
            pass
        except Exception:
            pass

    return 默认版本


__all__ = [
    "生成UUID",
    "生成机器人名称",
    "获取IPC路径",
    "获取本机IP",
    "检测机器人运控版本",
    "获取AP的Wifi名称",
    "获取项目版本",
]
