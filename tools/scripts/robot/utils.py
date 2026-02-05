import socket
import sys
import subprocess

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
