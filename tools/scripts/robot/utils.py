import socket
import sys
import subprocess
import configparser
from pathlib import Path

# 禁止输入的 IP 列表/前缀
BANNED_IPS = {"127.0.0.1", "192.168.234.1", "192.168.168.168"}

def 是否禁止IP(ip: str) -> bool:
    if ip in BANNED_IPS:
        return True
    return False

def 确保存在包(package_name, import_name=None):
    """
    package_name: pip 安装名
    import_name: import 名（默认等于 package_name）
    """
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
    except ImportError:
        print(f"📦 未检测到 {package_name}，正在自动安装...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", package_name
        ])
        print(f"✅ {package_name} 安装完成")

def 获取本地IP():
    """通过UDP连接获取本机对外的IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的建立连接，仅用于获取本机出口IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        # 增加异常处理，避免网络问题导致程序崩溃
        print(f"获取出口IP失败: {e}")
        ip = None
    finally:
        s.close()
    return ip

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "config.ini"


def 确保配置文件存在():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config["config_robot"] = {"robot_ip": "", "robot_port": ""}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)


def 读取机器狗配置():
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    section = config["config_robot"] if "config_robot" in config else {}
    robot_ip = section.get("robot_ip", "").strip() if section else ""
    robot_port_raw = section.get("robot_port", "").strip() if section else ""
    robot_port = int(robot_port_raw) if robot_port_raw.isdigit() else None
    return robot_ip or None, robot_port


def 写入机器狗配置(robot_ip: str, robot_port: int):
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    if "config_robot" not in config:
        config["config_robot"] = {}
    config["config_robot"]["robot_ip"] = robot_ip
    config["config_robot"]["robot_port"] = str(robot_port)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)
