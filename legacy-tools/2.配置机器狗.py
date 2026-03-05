"""
机器狗配置脚本
交互式配置菜单，支持软件安装和群控配置
"""

import fnmatch
import os
import re
import sys
import tarfile
import traceback
import zipfile
from pathlib import Path
from scripts.robot.utils import (
    确保存在包,
    是否禁止IP,
    获取本地IP,
    确保配置文件存在,
    读取机器狗配置,
    写入机器狗配置,
)

try:
    确保存在包("paramiko")
    确保存在包("ruamel.yaml")
    确保存在包("zeroconf")
except ImportError:
    sys.exit(1)

from scripts.robot.config import 机器狗配置器
from scripts.robot.robot_listener import 扫描设备

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
ROBOT_AGENT_ROOT = PROJECT_ROOT / "app" / "robot-agent"
PACKAGES_DIR = PROJECT_ROOT / "other" / "packages"

忽略模式 = [
    "__pycache__", "*.pyc", "*.pyo", "*.pyd",
    "*.egg-info", ".git", ".idea", ".vscode",
    ".DS_Store", "node_modules", "dist", "build",
    ".mypy_cache", ".ruff_cache",
]

def 解析压缩格式(raw_value: str) -> tuple[str, str]:
    """解析压缩格式"""
    value = raw_value.strip().lower()
    if value.startswith("."):
        value = value.lstrip(".")

    format_mapping = {
        "tar.gz": ("gztar", ".tar.gz"),
        "tgz": ("gztar", ".tar.gz"),
        "gztar": ("gztar", ".tar.gz"),
        "zip": ("zip", ".zip"),
        "tar": ("tar", ".tar"),
        "bztar": ("bztar", ".tar.bz2"),
        "tar.bz2": ("bztar", ".tar.bz2"),
        "xztar": ("xztar", ".tar.xz"),
        "tar.xz": ("xztar", ".tar.xz"),
    }

    if not value:
        return "gztar", ".tar.gz"

    if value in format_mapping:
        return format_mapping[value]

    print("✗ 未识别的压缩格式，已使用默认 tar.gz")
    return "gztar", ".tar.gz"


def 是否忽略路径(target: Path) -> bool:
    for part in target.parts:
        for pattern in 忽略模式:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def 写入压缩包(output_path: Path, source_dir: Path, archive_format: str) -> None:
    if output_path.exists():
        output_path.unlink()

    if archive_format == "zip":
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                dirs[:] = [d for d in dirs if not 是否忽略路径(root_path / d)]
                for file_name in files:
                    file_path = root_path / file_name
                    if 是否忽略路径(file_path):
                        continue
                    arcname = file_path.relative_to(source_dir).as_posix()
                    zip_file.write(file_path, arcname)
        return

    mode_mapping = {
        "gztar": "w:gz",
        "tar": "w",
        "bztar": "w:bz2",
        "xztar": "w:xz",
    }
    mode = mode_mapping.get(archive_format)
    if mode is None:
        raise ValueError(f"不支持的压缩格式: {archive_format}")

    with tarfile.open(output_path, mode) as tar_file:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not 是否忽略路径(root_path / d)]
            for file_name in files:
                file_path = root_path / file_name
                if 是否忽略路径(file_path):
                    continue
                arcname = file_path.relative_to(source_dir).as_posix()
                tar_file.add(file_path, arcname=arcname)


def 打包robot_agent套件(archive_format: str, ext: str) -> list[Path]:
    """打包 robot-agent 相关项目"""
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    projects = [
        ("robot-agent", ROBOT_AGENT_ROOT / "robot-agent"),
        ("robot-server", ROBOT_AGENT_ROOT / "robot-server"),
        ("sparkrobot-common", ROBOT_AGENT_ROOT / "sparkrobot-common"),
    ]
    outputs: list[Path] = []

    for name, path in projects:
        if not path.exists():
            print(f"✗ 找不到目录: {path}")
            continue
        output_path = PACKAGES_DIR / f"{name}{ext}"
        写入压缩包(output_path, path, archive_format)
        outputs.append(output_path)
        print(f"✓ 已生成: {output_path}")

    return outputs


def 执行打包流程(open_explorer: bool = True, require_prompt: bool = True) -> tuple[str, str, list[Path]]:
    print("\n" + "-"*50)
    print("打包 robot-agent 套件")
    print("-"*50)
    archive_format: str
    ext: str
    if require_prompt:
        print("支持格式: tar.gz(默认), zip, tar, tar.bz2, tar.xz")
        raw_format = input("请输入压缩格式 (回车默认 tar.gz): ")
        archive_format, ext = 解析压缩格式(raw_format)
    else:
        archive_format, ext = 解析压缩格式("tar.gz")

    outputs = 打包robot_agent套件(archive_format, ext)
    if outputs:
        print("\n" + "="*50)
        print("✓ 打包完成")
        print("="*50)
        if open_explorer:
            os.startfile(str(PACKAGES_DIR))
    else:
        print("\n" + "="*50)
        print("✗ 打包失败")
        print("="*50)
    return archive_format, ext, outputs

def execute_task(choice: str, robot_ip: str, robot_port: int, package_ext: str | None = None) -> bool:
    """执行配置任务"""
    print("\n" + "="*50)
    print("正在连接机器狗...")
    print("="*50)

    # 获取SSH认证信息
    用户名 = "firefly"
    密码 = "firefly"

    # 创建配置器
    configurator = 机器狗配置器(robot_port, robot_ip, 用户名, 密码)

    # 连接机器狗
    if not configurator.连接():
        print("\n✗ 无法连接到机器狗，请检查:")
        print("  1. 是否已连接到机器狗的 WIFI")
        print("  2. IP 地址是否正确")
        input("\n按回车键返回...")
        return False

    success = False
    try:
        # 执行配置
        if choice == "install_1":
            success = configurator.安装SparkRobotCommon(package_ext)
        elif choice == "install_2":
            success = configurator.安装RobotServer(package_ext)
        elif choice == "install_3":
            success = configurator.安装RobotAgent(package_ext)
        elif choice == "config_1_view":
            success = configurator.查看WIFI信息()
        elif choice == "config_1_modify":
            success = configurator.仅配置WIFI()
        elif choice == "config_2_modify":
            本机IP = 获取本地IP()
            if not 本机IP:
                print("✗ 无法自动获取本机 IP")
                success = False
            else:
                success = configurator.查看修改SDK配置(本机IP)
        elif choice == "config_2_view":
            configurator.查看SDK配置()
            success = True
        elif choice == "config_2_reset":
            success = configurator.重置SDK配置()
        elif choice == "config_3_modify":
            success = configurator.查看修改运控配置(robot_ip)
        elif choice == "config_3_view":
            configurator.查看运控配置()
            success = True
        elif choice == "config_3_reset":
            success = configurator.重置运控配置()
        elif choice == "config_4":
            success = configurator.重启运动控制()
        elif choice == "main_4":
            success = configurator.SSH登录()
        else:
            print(f"✗ 未知的选项: {choice}")
            success = False

        if success:
            print("\n" + "="*50)
            print("✓ 任务完成！")
            print("="*50)
        else:
            print("\n" + "="*50)
            print("✗ 任务失败或取消")
            print("="*50)

    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        traceback.print_exc()
        success = False
    finally:
        configurator.断开连接()

    input("\n按回车键返回上级菜单...")
    return success


def main():
    print("\033]0;配置机器狗\007")
    """主函数"""
    print("="*50)
    print("机器狗配置脚本")
    print("="*50)

    try:
        确保配置文件存在()

        # 交互式模式
        while True:
            # 读取当前配置
            current_ip, current_port = 读取机器狗配置()
            current_config_str = f" (当前: {current_ip}:{current_port})" if current_ip and current_port else ""

            print("\n" + "="*50)
            print("机器狗配置主菜单")
            print("="*50)
            print(f"1. 修改配置{current_config_str}")
            print("2. 安装软件")
            print("3. 群控配置")
            print("4. SSH 登录")
            print("5. 扫描设备")
            print("6. 打包 robot-agent 套件")
            print("0. 退出脚本")

            main_choice = input("\n请输入选项 (0/1/2/3/4/5/6): ").strip()

            if main_choice == "0":
                print("再见！")
                break

            if main_choice == "1":
                while True:
                    print("注意: 自身AP 192.168.234.1，有线 192.168.168.168")
                    prompt = f"\n请输入机器狗 IP (当前: {current_ip}，回车不修改): " if current_ip else "\n请输入机器狗 IP: "
                    机器人IP = input(prompt).strip()

                    if not 机器人IP:
                        if current_ip:
                            机器人IP = current_ip
                            print(f"使用当前 IP: {机器人IP}")
                        else:
                            continue

                    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", 机器人IP):
                        print("✗ IP 地址格式无效，请重新输入")
                        continue
                    if 是否禁止IP(机器人IP):
                        print("✗ 此 IP 不允许作为输入")
                        continue
                    break

                while True:
                    prompt = f"请输入端口号 (当前: {current_port}, 默认: 43988，回车不修改): " if current_port else "请输入端口号 (默认: 43988): "
                    本机端口号_str = input(prompt).strip()

                    if not 本机端口号_str:
                        if current_port:
                            本机端口号 = current_port
                            print(f"使用当前端口: {本机端口号}")
                            break
                        else:
                            本机端口号 = 43988
                            print("使用默认端口: 43988")
                            break

                    try:
                        本机端口号 = int(本机端口号_str)
                        if 1 <= 本机端口号 <= 65535:
                            break
                        else:
                            print("✗ 端口号必须在 1-65535 之间")
                    except ValueError:
                        print("✗ 请输入有效的数字")

                写入机器狗配置(机器人IP, 本机端口号)
                print("✓ 配置已保存")
                continue

            if main_choice == "6":
                执行打包流程()
                continue

            # 对于选项 2 和 3，需要先读取配置
            robot_ip, robot_port = 读取机器狗配置()
            if not robot_ip or not robot_port:
                print("✗ 请先在主菜单中配置机器狗 IP 和端口号 (选项 1)")
                continue

            if main_choice == "2":
                _, package_ext, outputs = 执行打包流程(open_explorer=False, require_prompt=False)
                if not outputs:
                    continue
                while True:
                    print("\n" + "-"*50)
                    print("安装软件")
                    print("-"*50)
                    print("1. 安装 sparkrobot-common")
                    print("2. 安装 robot-server")
                    print("3. 安装 robot-agent")
                    print("0. 返回主菜单")

                    install_choice = input("\n请输入选项 (0/1/2/3): ").strip()

                    if install_choice == "0":
                        break
                    elif install_choice == "1":
                        execute_task("install_1", robot_ip, robot_port, package_ext)
                    elif install_choice == "2":
                        execute_task("install_2", robot_ip, robot_port, package_ext)
                    elif install_choice == "3":
                        execute_task("install_3", robot_ip, robot_port, package_ext)
                    else:
                        print("✗ 无效的选项")

            elif main_choice == "3":
                # 群控配置子菜单
                while True:
                    print("\n" + "-"*50)
                    print("群控配置")
                    print("-"*50)
                    print("1. 修改 WIFI")
                    print("2. 修改 sdk 配置")
                    print("3. 修改 运控文件 配置")
                    print("4. 重启运控")
                    print("0. 返回主菜单")

                    config_choice = input("\n请输入选项 (0/1/2/3/4): ").strip()

                    if config_choice == "0":
                        break
                    elif config_choice == "1":
                        print("\n请选择 WIFI 操作:")
                        print("1. 查看当前 WIFI 信息")
                        print("2. 连接新 WIFI")
                        print("0. 返回")
                        net_choice = input("请输入选项 (0/1/2): ").strip()
                        if net_choice == "1":
                            execute_task("config_1_view", robot_ip, robot_port)
                        elif net_choice == "2":
                            execute_task("config_1_modify", robot_ip, robot_port)
                        elif net_choice == "0":
                            pass
                        else:
                            print("✗ 无效的选项")

                    elif config_choice == "2":
                        while True:
                            print("\n请选择 SDK 配置操作:")
                            print("1. 修改")
                            print("2. 查看")
                            print("3. 重置")
                            print("0. 返回")
                            sdk_choice = input("请输入选项 (0/1/2/3): ").strip()
                            if sdk_choice == "0":
                                break
                            elif sdk_choice == "1":
                                execute_task("config_2_modify", robot_ip, robot_port)
                            elif sdk_choice == "2":
                                execute_task("config_2_view", robot_ip, robot_port)
                            elif sdk_choice == "3":
                                execute_task("config_2_reset", robot_ip, robot_port)
                            else:
                                print("✗ 无效的选项")

                    elif config_choice == "3":
                        while True:
                            print("\n请选择运控配置操作:")
                            print("1. 修改")
                            print("2. 查看")
                            print("3. 重置")
                            print("0. 返回")
                            motion_choice = input("请输入选项 (0/1/2/3): ").strip()
                            if motion_choice == "0":
                                break
                            elif motion_choice == "1":
                                execute_task("config_3_modify", robot_ip, robot_port)
                            elif motion_choice == "2":
                                execute_task("config_3_view", robot_ip, robot_port)
                            elif motion_choice == "3":
                                execute_task("config_3_reset", robot_ip, robot_port)
                            else:
                                print("✗ 无效的选项")

                    elif config_choice == "4":
                        execute_task("config_4", robot_ip, robot_port)
                    else:
                        print("✗ 无效的选项，请重新输入")

            elif main_choice == "4":
                execute_task("main_4", robot_ip, robot_port)

            elif main_choice == "5":
                扫描设备()

            else:
                print("✗ 无效的选项，请重新输入")

    except (KeyboardInterrupt, EOFError):
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
