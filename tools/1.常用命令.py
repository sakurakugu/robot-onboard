import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from scripts.robot.package_builder import 执行打包流程
from scripts.robot.utils import 确保存在包, 读取机器狗配置, 写入机器狗配置

# 配置
ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TOOLS_DIR / "scripts"
PROJECT_ROOT = TOOLS_DIR.parent
BACKUPS_DIR = PROJECT_ROOT.parent / "backups"
CONFIG_FILE = SCRIPTS_DIR / "config" / "config.ini"

ROBOT_USER = "firefly"
DEFAULT_ROBOT_PORT = 43988

命令行安装任务映射 = {
    "common": "install_common",
    "server": "install_server",
    "agent": "install_agent",
    "runtime": "install_runtime",
    "ros": "install_ros",
    "full": "install_full",
}

命令行打包任务映射 = {
    "common": (["sparkrobot-common"], "打包 sparkrobot-common"),
    "server": (["robot-server"], "打包 robot-server"),
    "agent": (["robot-agent"], "打包 robot-agent"),
    "runtime": (["robot-runtime"], "打包 robot-runtime"),
    "ros": (["robot-ros"], "打包 robot-ros 工作区"),
    "full": (
        ["sparkrobot-common", "robot-server", "robot-agent", "robot-runtime", "robot-ros"],
        "打包本体全套",
    ),
}

# 颜色代码 (Windows 10+ 终端支持 ANSI 转义序列)
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    RED = '\033[0;31m'
    YELLOW = '\033[0;33m'
    NC = '\033[0m'

def print_info(msg: str):
    print(f"{Colors.BLUE}[信息]{Colors.NC} {msg}")

def print_success(msg: str):
    print(f"{Colors.GREEN}[成功]{Colors.NC} {msg}")

def print_error(msg: str):
    print(f"{Colors.RED}[错误]{Colors.NC} {msg}")

def print_warn(msg: str):
    print(f"{Colors.YELLOW}[警告]{Colors.NC} {msg}")

# --- 确保环境 ---

def 确保_git_hooks_已启用() -> None:
    """检查并启用 git hooks。"""
    # 检查 .githooks 目录是否存在
    githooks_dir = ROOT_DIR / ".githooks"
    if not githooks_dir.exists():
        return

    # 获取当前 hooks 路径
    result = subprocess.run(
        ["git", "config", "core.hooksPath"],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
    )
    current_path = result.stdout.strip() if result.returncode == 0 else ""

    # 如果已经设置为 .githooks，则跳过
    if current_path == ".githooks":
        return

    # print_info("启用 git hooks")
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        check=True,
        cwd=ROOT_DIR,
    )

    # 非 Windows 系统需要添加执行权限
    if os.name != "nt":
        for hook_file in githooks_dir.iterdir():
            if hook_file.is_file():
                subprocess.run(
                    ["chmod", "+x", str(hook_file)],
                    check=False,
                    cwd=ROOT_DIR,
                )

# --- 配置文件管理 ---

def 确保配置文件存在():
    """确保配置文件存在"""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config['robots'] = {'robot1': '192.168.1.106'}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        print_info(f"已创建配置文件: {CONFIG_FILE}")

def load_robots() -> Dict[str, str]:
    """从配置文件加载机器狗列表"""
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')

    if 'robots' not in config:
        return {}

    return dict(config['robots'])

def 保存机器狗列表(robots: Dict[str, str]):
    """保存机器狗列表到配置文件"""
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')

    config['robots'] = robots

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)


def 获取当前安装目标() -> Tuple[Optional[str], Optional[int]]:
    """读取当前安装软件使用的机器狗目标"""
    return 读取机器狗配置()


def 获取安装目标展示文本() -> str:
    """返回当前安装目标的展示文本"""
    robot_ip, robot_port = 获取当前安装目标()
    if robot_ip and robot_port:
        return f"{robot_ip}:{robot_port}"
    return "未设置"


def 输入端口号(current_port: Optional[int] = None) -> Optional[int]:
    """读取并校验端口号"""
    prompt = f"请输入端口号 (当前: {current_port}，回车保持不变): " if current_port else f"请输入端口号 (默认: {DEFAULT_ROBOT_PORT}): "

    while True:
        raw_port = input(prompt).strip()
        if not raw_port:
            if current_port:
                return current_port
            return DEFAULT_ROBOT_PORT

        try:
            port = int(raw_port)
        except ValueError:
            print_error("请输入有效的数字端口")
            continue

        if 1 <= port <= 65535:
            return port

        print_error("端口号必须在 1-65535 之间")


def 手动设置安装目标():
    """手动输入安装目标机器狗"""
    current_ip, current_port = 获取当前安装目标()

    while True:
        prompt = f"请输入机器狗 IP (当前: {current_ip}，回车保持不变): " if current_ip else "请输入机器狗 IP: "
        robot_ip = input(prompt).strip()

        if not robot_ip:
            if current_ip:
                robot_ip = current_ip
            else:
                print_error("IP 地址不能为空")
                continue

        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", robot_ip):
            break

        print_error("无效的 IP 地址格式")

    robot_port = 输入端口号(current_port)
    if robot_port is None:
        return

    写入机器狗配置(robot_ip, robot_port)
    print_success(f"已设置安装目标: {robot_ip}:{robot_port}")


def 从已保存机器狗设置安装目标():
    """从已保存机器狗列表中选择安装目标"""
    robots = load_robots()
    if not robots:
        print_error("暂无已保存机器狗，请先在设置中添加")
        return

    print("\n------------------------------------------")
    print("选择安装目标机器狗")
    print("------------------------------------------")
    for idx, (name, ip) in enumerate(robots.items(), 1):
        print(f"  {idx}) {name} ({ip})")
    print("  0) 返回")
    print("------------------------------------------")

    choice = input("请输入编号: ").strip()
    if choice == "0":
        return
    if not choice.isdigit():
        print_error("无效输入")
        return

    idx = int(choice)
    robot_list = list(robots.items())
    if not (1 <= idx <= len(robot_list)):
        print_error("无效的编号")
        return

    _, robot_ip = robot_list[idx - 1]
    _, current_port = 获取当前安装目标()
    robot_port = 输入端口号(current_port)
    if robot_port is None:
        return

    写入机器狗配置(robot_ip, robot_port)
    print_success(f"已设置安装目标: {robot_ip}:{robot_port}")


def 设置安装目标菜单():
    """设置安装目标机器狗"""
    while True:
        print("\n------------------------------------------")
        print("设置安装目标机器狗")
        print("------------------------------------------")
        print(f"当前目标: {获取安装目标展示文本()}")
        print("  1) 从已保存机器狗选择")
        print("  2) 手动输入 IP 和端口")
        print("  0) 返回")
        print("------------------------------------------")

        choice = input("请选择: ").strip()
        if choice == "0":
            return
        if choice == "1":
            从已保存机器狗设置安装目标()
            return
        if choice == "2":
            手动设置安装目标()
            return

        print_error("无效选项")

# --- 功能函数 ---

def 机器狗列表菜单():
    """机器狗列表菜单"""
    while True:
        robots = load_robots()

        print("\n------------------------------------------")
        print("    机器狗列表")
        print("------------------------------------------")

        if not robots:
            print("  (暂无机器狗，请先添加)")
        else:
            for idx, (name, ip) in enumerate(robots.items(), 1):
                print(f"  {idx}) {name} ({ip})")

        print("------------------------------------------")
        print("  a) 添加机器狗")
        print("  0) 返回主菜单")
        print("------------------------------------------")

        choice = input("请选择要连接的机器狗 (输入编号) 或操作: ").strip().lower()

        if choice == "0":
            return
        elif choice == "a":
            添加机器狗()
        elif choice.isdigit():
            idx = int(choice)
            robot_list = list(robots.items())
            if 1 <= idx <= len(robot_list):
                name, ip = robot_list[idx - 1]
                连接机器狗(name, ip)
            else:
                print_error("无效的编号")
        else:
            print_error("无效选项")

def 添加机器狗():
    """添加新机器狗"""
    robots = load_robots()

    print("\n------------------------------------------")
    print("添加新机器狗")
    print("------------------------------------------")

    name = input("请输入机器狗名称 (如 robot1): ").strip()
    if not name:
        print_error("名称不能为空")
        return

    if name in robots:
        print_error(f"名称 '{name}' 已存在")
        return

    ip = input("请输入机器狗 IP 地址: ").strip()
    if not ip:
        print_error("IP 地址不能为空")
        return

    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        print_error("无效的 IP 地址格式")
        return

    robots[name] = ip
    保存机器狗列表(robots)
    print_success(f"已添加机器狗: {name} ({ip})")

def 运行ssh命令(command: List[str], use_sshpass: bool):
    """运行 SSH 命令"""
    if use_sshpass:
        return subprocess.run(["sshpass", "-p", "firefly"] + command)
    return subprocess.run(command)

def 连接机器狗(name: str, ip: str):
    """连接机器狗"""
    print_info(f"正在连接机器狗 {name} ({ROBOT_USER}@{ip})...")
    use_sshpass: bool = sys.platform != "win32" and bool(shutil.which("sshpass"))
    ssh_cmd = ["ssh", f"{ROBOT_USER}@{ip}"]
    try:
        运行ssh命令(ssh_cmd, use_sshpass)
    except FileNotFoundError:
        print_error("未找到 ssh 命令，请确保已安装 OpenSSH Client")


def 输出ROS安装前提示() -> None:
    """输出 robot-ros 安装前的雷达网络提示。"""
    print_warn("当前推荐把网口雷达放到独立有线网段")
    print("  推荐配置:")
    print("    机器狗 eth0: 192.168.168.168/24")
    print("    雷达 IP: 192.168.168.200")
    print("    雷达数据目标 IP: 192.168.168.168")
    print("  不再推荐给 eth0 额外挂 192.168.1.102/24")
    print("  若 wlan0 也在 192.168.1.x，同机双网卡落在同一子网会导致 SSH 回包走错")
    print("  若雷达仍是厂商默认 192.168.1.200，请先用上位机改到 192.168.168.200")


def 执行安装任务(
    task_name: str,
    robot_ip: str,
    robot_port: int,
    package_ext: str | None = None,
    pause_after: bool = True,
) -> bool:
    """执行机器狗软件安装任务"""
    if task_name in {"install_ros", "install_full"}:
        输出ROS安装前提示()

    try:
        确保存在包("paramiko")
        确保存在包("ruamel.yaml")
    except ImportError:
        print_error("依赖安装失败，无法继续执行安装")
        return False

    from scripts.robot.config import 机器狗配置器

    print("\n" + "=" * 50)
    print("正在连接机器狗...")
    print("=" * 50)

    configurator = 机器狗配置器(robot_port, robot_ip, ROBOT_USER, ROBOT_USER)
    if not configurator.连接():
        print_error("无法连接到机器狗，请检查网络、IP 和端口是否正确")
        if pause_after:
            input("\n按回车键返回安装菜单...")
        return False

    success = False
    try:
        if task_name == "install_common":
            success = configurator.安装SparkRobotCommon(package_ext)
        elif task_name == "install_server":
            success = configurator.安装RobotServer(package_ext)
        elif task_name == "install_agent":
            success = configurator.安装RobotAgent(package_ext)
        elif task_name == "install_runtime":
            success = configurator.安装RobotRuntime(package_ext)
        elif task_name == "install_ros":
            success = configurator.安装RobotRos工作区(package_ext)
        elif task_name == "install_full":
            success = configurator.安装本体全套(package_ext)
        else:
            print_error(f"未知的安装任务: {task_name}")

        if success:
            print_success("安装完成")
        else:
            print_error("安装失败或已取消")
    except Exception as e:
        print_error(f"安装过程中发生错误: {e}")
        traceback.print_exc()
        success = False
    finally:
        configurator.断开连接()

    if pause_after:
        input("\n按回车键返回安装菜单...")
    return success


def 安装软件菜单():
    """安装机器狗软件菜单"""
    while True:
        current_target = 获取安装目标展示文本()

        print("\n------------------------------------------")
        print("安装机器狗软件")
        print("------------------------------------------")
        print(f"当前目标: {current_target}")
        print("说明: 安装会先在本地自动打包，再上传并部署到目标机器狗")
        print("  1) 设置安装目标机器狗")
        print("  2) 安装 sparkrobot-common")
        print("  3) 安装 robot-server")
        print("  4) 安装 robot-agent")
        print("  5) 安装 robot-runtime 服务")
        print("  6) 安装 robot-ros 工作区（含 rosdep / colcon）")
        print("  7) 一键打包并安装本体全套")
        print("  0) 返回")
        print("------------------------------------------")

        choice = input("请选择: ").strip()
        if choice == "0":
            return

        if choice == "1":
            设置安装目标菜单()
            continue

        robot_ip, robot_port = 获取当前安装目标()
        if not robot_ip or not robot_port:
            print_error("请先设置安装目标机器狗")
            continue

        if choice == "2":
            执行安装任务("install_common", robot_ip, robot_port)
        elif choice == "3":
            执行安装任务("install_server", robot_ip, robot_port)
        elif choice == "4":
            执行安装任务("install_agent", robot_ip, robot_port)
        elif choice == "5":
            执行安装任务("install_runtime", robot_ip, robot_port)
        elif choice == "6":
            执行安装任务("install_ros", robot_ip, robot_port)
        elif choice == "7":
            执行安装任务("install_full", robot_ip, robot_port)
        else:
            print_error("无效选项")


def 执行打包任务(
    project_names: List[str],
    title: str,
    package_format: str = "tar.gz",
    require_prompt: bool = True,
    open_explorer: bool = True,
) -> bool:
    """执行指定项目打包任务"""
    _, _, outputs = 执行打包流程(
        project_names=project_names,
        title=title,
        package_format=package_format,
        require_prompt=require_prompt,
        open_explorer=open_explorer,
    )
    return bool(outputs)


def 打包本体软件菜单():
    """打包本体软件菜单"""
    while True:
        print("\n------------------------------------------")
        print("打包本体软件（本地）")
        print("------------------------------------------")
        print("  1) 一键打包本体全套")
        print("  2) 打包 sparkrobot-common")
        print("  3) 打包 robot-server")
        print("  4) 打包 robot-agent")
        print("  5) 打包 robot-runtime")
        print("  6) 打包 robot-ros 工作区")
        print("  0) 返回")
        print("------------------------------------------")

        choice = input("请选择: ").strip()
        if choice == "0":
            return
        if choice == "1":
            执行打包任务(
                ["sparkrobot-common", "robot-server", "robot-agent", "robot-runtime", "robot-ros"],
                "打包本体全套",
            )
            return
        if choice == "2":
            执行打包任务(["sparkrobot-common"], "打包 sparkrobot-common")
            return
        if choice == "3":
            执行打包任务(["robot-server"], "打包 robot-server")
            return
        if choice == "4":
            执行打包任务(["robot-agent"], "打包 robot-agent")
            return
        if choice == "5":
            执行打包任务(["robot-runtime"], "打包 robot-runtime")
            return
        if choice == "6":
            执行打包任务(["robot-ros"], "打包 robot-ros 工作区")
            return

        print_error("无效选项")


def 解析命令行参数() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="机器狗本体常用命令工具",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "示例:\n"
            "  python tools\\1.常用命令.py --package full --format zip\n"
            "  python tools\\1.常用命令.py --install full --robot-ip 192.168.1.106\n"
            "  python tools\\1.常用命令.py --robot-ip 192.168.1.106 --robot-port 43988 --save-target"
        ),
    )
    parser.add_argument("--robot-ip", help="目标机器狗 IP")
    parser.add_argument("--robot-port", type=int, help=f"目标机器狗端口，默认 {DEFAULT_ROBOT_PORT}")
    parser.add_argument("--save-target", action="store_true", help="保存 --robot-ip / --robot-port 为默认安装目标")
    parser.add_argument(
        "--install",
        choices=sorted(命令行安装任务映射.keys()),
        help="执行远程安装任务：common/server/agent/runtime/ros/full",
    )
    parser.add_argument(
        "--package",
        choices=sorted(命令行打包任务映射.keys()),
        help="执行本地打包任务：common/server/agent/runtime/ros/full",
    )
    parser.add_argument("--format", default="tar.gz", help="打包格式，支持 tar.gz、zip、tar、tar.bz2、tar.xz")
    return parser.parse_args()


def 校验命令行IP(robot_ip: str) -> bool:
    """校验命令行传入的 IP 地址"""
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", robot_ip))


def 获取命令行安装目标(robot_ip: Optional[str], robot_port: Optional[int]) -> Tuple[Optional[str], int]:
    """获取命令行安装目标"""
    saved_ip, saved_port = 获取当前安装目标()
    target_ip = robot_ip or saved_ip

    if robot_port is not None:
        return target_ip, robot_port
    if saved_port is not None:
        return target_ip, saved_port
    return target_ip, DEFAULT_ROBOT_PORT


def 执行命令行模式(args: argparse.Namespace) -> int:
    """执行命令行模式"""
    if args.install and args.package:
        print_error("--install 和 --package 不能同时使用")
        return 1

    if args.robot_ip and not 校验命令行IP(args.robot_ip):
        print_error("命令行传入的 --robot-ip 格式无效")
        return 1
    if args.robot_port is not None and not (1 <= args.robot_port <= 65535):
        print_error("命令行传入的 --robot-port 必须在 1-65535 之间")
        return 1

    target_ip, target_port = 获取命令行安装目标(args.robot_ip, args.robot_port)

    if args.save_target:
        if not target_ip:
            print_error("保存默认目标前，请提供 --robot-ip")
            return 1
        写入机器狗配置(target_ip, target_port)
        print_success(f"已保存默认安装目标: {target_ip}:{target_port}")

    if args.package:
        project_names, title = 命令行打包任务映射[args.package]
        success = 执行打包任务(
            project_names=project_names,
            title=title,
            package_format=args.format,
            require_prompt=False,
            open_explorer=False,
        )
        return 0 if success else 1

    install_task_name: Optional[str] = None
    if args.install:
        install_task_name = 命令行安装任务映射[args.install]

    if install_task_name:
        if not target_ip:
            print_error("执行远程任务前，请提供 --robot-ip，或先保存默认安装目标")
            return 1
        success = 执行安装任务(
            task_name=install_task_name,
            robot_ip=target_ip,
            robot_port=target_port,
            package_ext=args.format,
            pause_after=False,
        )
        return 0 if success else 1

    if args.save_target:
        return 0

    print_error("未指定任何任务，请使用 --install、--package 或 --save-target")
    return 1

def 获取当前时间戳() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

def 备份文件(source_dir: Path, dest_dir: Path, ignore_patterns: Optional[List[str]] = None):
    """使用 shutil.copytree 进行备份"""
    try:
        if ignore_patterns:
            shutil.copytree(source_dir, dest_dir, ignore=shutil.ignore_patterns(*ignore_patterns))
        else:
            shutil.copytree(source_dir, dest_dir)
        print_success(f"备份完成: {dest_dir}")
    except Exception as e:
        print_error(f"备份失败: {e}")

def 备份git文件(source_dir: Path, dest_dir: Path):
    """仅备份 git 管理的文件"""
    try:
        # 获取 git 文件列表
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=source_dir,
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.splitlines()

        print_info(f"检测到 {len(files)} 个受版本控制的文件")

        for rel_path in files:
            src_file = source_dir / rel_path
            dst_file = dest_dir / rel_path

            if src_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

        print_success(f"Git 文件备份完成: {dest_dir}")

    except subprocess.CalledProcessError:
        print_warn("获取 Git 文件列表失败，可能不是 Git 仓库。回退到完整备份。")
        备份文件(source_dir, dest_dir)
    except Exception as e:
        print_error(f"备份失败: {e}")

def 备份菜单():
    root_name = PROJECT_ROOT.name

    print("\n------------------------------------------")
    print("备份选项:")
    print("  1) 备份全部")
    print("  2) 排除常见目录 (node_modules, dist, venv, etc.)")
    print("  3) 按 .gitignore 排除 (仅备份 Git 追踪文件)")
    print("------------------------------------------")

    choice = input("请选择备份类型: ").strip()

    if choice not in ["1", "2", "3"]:
        print_error("无效选项")
        return

    name = input(f"备份目录名(回车使用默认: {root_name}): ").strip() or root_name
    timestamp = 获取当前时间戳()
    dest_path = BACKUPS_DIR / name / timestamp

    print_info(f"目标路径: {dest_path}")

    if choice == "1":
        备份文件(PROJECT_ROOT, dest_path)
    elif choice == "2":
        ignores = [
            "node_modules", "build", "__pycache__", "dist",
            ".venv", "venv", ".pytest_cache", ".git", ".idea", ".vscode"
        ]
        备份文件(PROJECT_ROOT, dest_path, ignores)
    elif choice == "3":
        备份git文件(PROJECT_ROOT, dest_path)

def 修复git_refs():
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        print_error("未检测到 .git 目录")
        return

    # 修复 Windows 可能出现的 Zone.Identifier 文件
    bad_ref = git_dir / "refs" / "heads" / "main:Zone.Identifier"
    if bad_ref.exists():
        try:
            os.remove(bad_ref)
            print_success("已删除 refs/heads/main:Zone.Identifier")
        except Exception as e:
            print_error(f"删除文件失败: {e}")

    packed_refs = git_dir / "packed-refs"
    if packed_refs.exists():
        try:
            content = packed_refs.read_text(encoding="utf-8")
            if "main:Zone.Identifier" in content:
                new_content = "\n".join([line for line in content.splitlines() if "main:Zone.Identifier" not in line])
                packed_refs.write_text(new_content, encoding="utf-8")
                print_success("已清理 packed-refs 中的异常引用")
        except Exception as e:
            print_error(f"处理 packed-refs 失败: {e}")

    try:
        subprocess.run(["git", "fetch", "--prune", "--tags", "origin"], cwd=PROJECT_ROOT, check=False)
        print_success("已执行 git fetch --prune")
    except Exception:
        pass

def 修改git上次提交日志():
    if not (PROJECT_ROOT / ".git").exists():
        print_error("不是 Git 仓库")
        return

    try:
        # 获取当前分支
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=PROJECT_ROOT, text=True).strip()
        print_info(f"当前分支: {branch}")

        input("按回车开始修改（Git 默认编辑器）: ")
        subprocess.run(["git", "commit", "--amend"], cwd=PROJECT_ROOT)
        print_success("已更新上次提交日志")

        choice = input("是否需要安全推送 (git push --force-with-lease)? (y/N): ").strip().lower()
        if choice == "y":
            ret = subprocess.run(["git", "push", "--force-with-lease"], cwd=PROJECT_ROOT)
            if ret.returncode == 0:
                print_success("已安全推送更新")
            else:
                print_error("推送失败")

    except Exception as e:
        print_error(f"操作失败: {e}")

def 修复常见错误():
    print("\n------------------------------------------")
    print("修复常见错误:")
    print("  1) 修复 Git refs/heads/main:Zone.Identifier")
    print("  2) 修改 Git 上次提交日志 (amend)")
    print("  3) 修复 Gradle 缺失的 Eclipse Buildship 配置")
    print("  0) 返回")
    print("------------------------------------------")

    choice = input("请选择修复项: ").strip()
    if choice == "1":
        修复git_refs()
    elif choice == "2":
        修改git上次提交日志()
    elif choice == "3":
        修复gradle_buildship_configs()
    elif choice == "0":
        return
    else:
        print_error("无效选项")

def 修复gradle_buildship_configs():
    """修复 Gradle 项目缺失的 Eclipse Buildship 配置文件"""
    print("\n------------------------------------------")
    print("修复 Gradle Buildship 配置:")
    print("  1) 自动修复 React Native Gradle Plugin")
    print("  2) 扫描整个工作区")
    print("  3) 指定目录")
    print("  4) 预览模式（不实际创建文件）")
    print("  0) 返回")
    print("------------------------------------------")

    choice = input("请选择: ").strip()
    script_path = SCRIPTS_DIR / "fix" / "fix_gradle_settings.py"

    if choice == "1":
        print_info("正在修复 React Native Gradle Plugin...")
        result = subprocess.run([sys.executable, str(script_path)],
                              cwd=PROJECT_ROOT,
                              capture_output=False)
        if result.returncode == 0:
            print_success("修复完成！")
        else:
            print_error("修复失败")

    elif choice == "2":
        print_info("正在扫描整个工作区...")
        result = subprocess.run([sys.executable, str(script_path), "--scan-all"],
                              cwd=PROJECT_ROOT,
                              capture_output=False)
        if result.returncode == 0:
            print_success("扫描完成！")
        else:
            print_error("扫描失败")

    elif choice == "3":
        target_dir = input("请输入目录路径: ").strip()
        if target_dir:
            print_info(f"正在修复目录: {target_dir}")
            result = subprocess.run([sys.executable, str(script_path), "--path", target_dir],
                                  cwd=PROJECT_ROOT,
                                  capture_output=False)
            if result.returncode == 0:
                print_success("修复完成！")
            else:
                print_error("修复失败")
        else:
            print_error("目录路径不能为空")

    elif choice == "4":
        print_info("预览模式 - 不会实际创建文件")
        result = subprocess.run([sys.executable, str(script_path), "--dry-run"],
                              cwd=PROJECT_ROOT,
                              capture_output=False)

    elif choice == "0":
        return
    else:
        print_error("无效选项")

def 检查代码注释():
    """运行 check_comments.py 扫描根目录"""
    script_path = SCRIPTS_DIR / "hook" / "check_comments.py"
    if not script_path.exists():
        print_error(f"找不到脚本: {script_path}")
        return

    print_info("正在扫描代码注释 (根目录)...")
    try:
        # 使用当前 python 解释器运行脚本，并传递 --all 参数
        subprocess.run([sys.executable, str(script_path), "--all"], cwd=PROJECT_ROOT)
    except Exception as e:
        print_error(f"运行失败: {e}")

def 设置菜单():
    """设置菜单 - 管理机器狗配置"""
    while True:
        robots = load_robots()

        print("\n------------------------------------------")
        print("    设置 - 机器狗管理")
        print("------------------------------------------")

        if not robots:
            print("  (暂无机器狗)")
        else:
            for idx, (name, ip) in enumerate(robots.items(), 1):
                print(f"  {idx}) {name} = {ip}")

        print("------------------------------------------")
        print("  a) 添加机器狗")
        print("  e) 编辑机器狗 (修改名称或IP)")
        print("  d) 删除机器狗")
        print("  0) 返回主菜单")
        print("------------------------------------------")

        choice = input("请选择操作: ").strip().lower()

        if choice == "0":
            return
        elif choice == "a":
            添加机器狗()
        elif choice == "e":
            编辑机器狗()
        elif choice == "d":
            删除机器狗()
        else:
            print_error("无效选项")

def 编辑机器狗():
    """编辑机器狗配置"""
    robots = load_robots()

    if not robots:
        print_error("暂无机器狗可编辑")
        return

    print("\n------------------------------------------")
    print("选择要编辑的机器狗:")
    print("------------------------------------------")

    for idx, (name, ip) in enumerate(robots.items(), 1):
        print(f"  {idx}) {name} = {ip}")

    print("------------------------------------------")

    choice = input("请输入编号: ").strip()

    if not choice.isdigit():
        print_error("无效输入")
        return

    idx = int(choice)
    robot_list = list(robots.items())

    if not (1 <= idx <= len(robot_list)):
        print_error("无效的编号")
        return

    old_name, old_ip = robot_list[idx - 1]

    print(f"\n当前: {old_name} = {old_ip}")
    print("------------------------------------------")
    print("  1) 修改名称")
    print("  2) 修改 IP")
    print("  3) 同时修改名称和 IP")
    print("  0) 取消")
    print("------------------------------------------")

    edit_choice = input("请选择: ").strip()

    if edit_choice == "0":
        return
    elif edit_choice == "1":
        new_name = input(f"请输入新名称 (当前: {old_name}): ").strip()
        if not new_name:
            print_error("名称不能为空")
            return
        if new_name != old_name and new_name in robots:
            print_error(f"名称 '{new_name}' 已存在")
            return
        # 删除旧键，添加新键
        del robots[old_name]
        robots[new_name] = old_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' 改名为 '{new_name}'")

    elif edit_choice == "2":
        new_ip = input(f"请输入新 IP (当前: {old_ip}): ").strip()
        if not new_ip:
            print_error("IP 不能为空")
            return
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", new_ip):
            print_error("无效的 IP 地址格式")
            return
        robots[old_name] = new_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' 的 IP 修改为 '{new_ip}'")

    elif edit_choice == "3":
        new_name = input(f"请输入新名称 (当前: {old_name}): ").strip()
        if not new_name:
            print_error("名称不能为空")
            return
        if new_name != old_name and new_name in robots:
            print_error(f"名称 '{new_name}' 已存在")
            return

        new_ip = input(f"请输入新 IP (当前: {old_ip}): ").strip()
        if not new_ip:
            print_error("IP 不能为空")
            return
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", new_ip):
            print_error("无效的 IP 地址格式")
            return

        del robots[old_name]
        robots[new_name] = new_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' ({old_ip}) 修改为 '{new_name}' ({new_ip})")
    else:
        print_error("无效选项")

def 删除机器狗():
    """删除机器狗"""
    robots = load_robots()

    if not robots:
        print_error("暂无机器狗可删除")
        return

    print("\n------------------------------------------")
    print("选择要删除的机器狗:")
    print("------------------------------------------")

    for idx, (name, ip) in enumerate(robots.items(), 1):
        print(f"  {idx}) {name} = {ip}")

    print("------------------------------------------")

    choice = input("请输入编号: ").strip()

    if not choice.isdigit():
        print_error("无效输入")
        return

    idx = int(choice)
    robot_list = list(robots.items())

    if not (1 <= idx <= len(robot_list)):
        print_error("无效的编号")
        return

    name, ip = robot_list[idx - 1]

    confirm = input(f"确认删除 '{name}' ({ip})? (y/N): ").strip().lower()
    if confirm == "y":
        del robots[name]
        保存机器狗列表(robots)
        print_success(f"已删除机器狗: {name}")

def 显示菜单():
    robots = load_robots()
    robot_count = len(robots)

    print("\n==========================================")
    print("    机器狗项目 - 常用命令 (Python版)")
    print("==========================================")
    print(f"  1) SSH 连接机器狗 (已保存 {robot_count} 个)")
    print("  2) 备份当前项目文件夹")
    print("  3) 修复常见错误")
    print("  4) 检查代码注释 (默认扫描根目录)")
    print("  5) 设置 (管理机器狗)")
    print(f"  6) 安装机器狗软件 (当前目标: {获取安装目标展示文本()})")
    print("  7) 打包本体软件")
    print("  0) 退出")
    print("")
    print("==========================================")

def 运行交互模式():
    """运行交互模式"""
    while True:
        try:
            显示菜单()
            choice = input("请输入选项编号: ").strip()

            if choice == "1":
                机器狗列表菜单()
            elif choice == "2":
                备份菜单()
            elif choice == "3":
                修复常见错误()
            elif choice == "4":
                检查代码注释()
            elif choice == "5":
                设置菜单()
            elif choice == "6":
                安装软件菜单()
            elif choice == "7":
                打包本体软件菜单()
            elif choice == "0":
                print_success("退出脚本")
                sys.exit(0)
            else:
                print_error("无效选项，请重新选择")

            input("\n按回车键继续...")

        except KeyboardInterrupt:
            print("\n")
            print_success("退出脚本")
            sys.exit(0)


def main():
    命令行模式 = len(sys.argv) > 1

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not 命令行模式:
        print("\033]0;服务端\007")
        # 确保能够显示颜色
        os.system("")

    确保_git_hooks_已启用()
    确保配置文件存在()

    if 命令行模式:
        args = 解析命令行参数()
        sys.exit(执行命令行模式(args))

    运行交互模式()

if __name__ == "__main__":
    main()
