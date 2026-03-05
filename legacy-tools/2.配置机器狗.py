"""
机器狗配置脚本
交互式配置菜单，支持软件安装和群控配置
"""

import re
import sys
import traceback
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

def execute_task(choice: str, robot_ip: str, robot_port: int) -> bool:
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
            # 安装 sparkrobot-common
            success = configurator.安装SparkRobotCommon()
        elif choice == "install_2":
            # 安装 robot-server
            success = configurator.安装RobotServer()
        elif choice == "config_1_view":
            # 查看 WIFI 信息
            success = configurator.查看WIFI信息()
        elif choice == "config_1_modify":
            # 配置 WIFI
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
            # 重启运控
            success = configurator.重启运动控制()
        elif choice == "main_4":
            # SSH 登录
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
            print("0. 退出脚本")

            main_choice = input("\n请输入选项 (0/1/2/3/4/5): ").strip()

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

            # 对于选项 2 和 3，需要先读取配置
            robot_ip, robot_port = 读取机器狗配置()
            if not robot_ip or not robot_port:
                print("✗ 请先在主菜单中配置机器狗 IP 和端口号 (选项 1)")
                continue

            if main_choice == "2":
                # 安装软件子菜单
                while True:
                    print("\n" + "-"*50)
                    print("安装软件")
                    print("-"*50)
                    print("1. 安装 sparkrobot-common")
                    print("2. 安装 robot-server")
                    print("0. 返回主菜单")

                    install_choice = input("\n请输入选项 (0/1/2): ").strip()

                    if install_choice == "0":
                        break
                    elif install_choice == "1":
                        execute_task("install_1", robot_ip, robot_port)
                    elif install_choice == "2":
                        execute_task("install_2", robot_ip, robot_port)
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
