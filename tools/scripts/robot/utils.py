import socket
import sys
import os
import subprocess
import configparser
import importlib
import site
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
        
        def _install_pip():
            print("⚠️ 检测到 pip 未安装，正在尝试自动安装 pip...")
            try:
                # 尝试使用 apt 安装 pip (适用于 Ubuntu/Debian)
                subprocess.check_call(["sudo", "apt", "update"])
                subprocess.check_call(["sudo", "apt", "install", "-y", "python3-pip"])
                print("✅ pip 安装完成")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ 自动安装 pip 失败: {e}")
                return False
            except FileNotFoundError:
                print("❌ 未找到 apt 命令，无法自动安装 pip")
                return False

        try:
            # 尝试直接安装包
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package_name
            ])
            print(f"✅ {package_name} 安装完成")
            
            # 刷新环境并验证导入
            importlib.invalidate_caches()
            
            # 尝试重新加载 site-packages (特别是 ~/.local)
            importlib.reload(site)
            
            # 显式检查并添加用户 site-packages
            try:
                user_site = site.getusersitepackages()
                if os.path.exists(user_site) and user_site not in sys.path:
                    sys.path.append(user_site)
            except Exception:
                pass

            # 验证导入，如果失败则重启脚本
            try:
                __import__(import_name)
            except ImportError:
                print(f"🔄 检测到新环境配置，正在重启脚本以生效...")
                # 刷新 stdout 以确保日志输出完整
                sys.stdout.flush()
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except subprocess.CalledProcessError:
            # 如果安装失败，检查是否是因为 pip 缺失
            is_pip_missing = False
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                is_pip_missing = True
            
            if is_pip_missing:
                if _install_pip():
                    # 如果 pip 安装成功，重试安装包
                    try:
                        subprocess.check_call([
                            sys.executable, "-m", "pip", "install", package_name
                        ])
                        print(f"✅ {package_name} 安装完成")
                        
                        # 安装成功后重启脚本
                        print(f"🔄 环境已更新，正在重启脚本...")
                        sys.stdout.flush()
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    except subprocess.CalledProcessError:
                        pass # 继续执行下方的错误提示
            
            # 如果重试失败或不是因为 pip 缺失，显示手动安装提示
            print(f"\n❌ 自动安装 {package_name} 失败。")
            print(f"可能是因为环境中没有安装 pip，或者网络问题。")
            print(f"请尝试手动运行以下命令安装:")
            print(f"  sudo apt update && sudo apt install python3-pip")
            print(f"  pip3 install {package_name}")
            raise ImportError(f"无法安装必需的包: {package_name}")

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
