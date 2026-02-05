"""
机器狗配置脚本
交互式配置菜单，支持软件安装和群控配置
"""

import re
from scripts.robot.utils import (
    确保存在包,
    是否禁止IP,
    获取本地IP,
    确保配置文件存在,
    读取机器狗配置,
    写入机器狗配置,
)

确保存在包("paramiko")
确保存在包("ruamel.yaml")

from scripts.robot.config import 机器狗配置器


def main():
    """主函数"""
    print("="*50)
    print("机器狗配置脚本")
    print("="*50)
    
    try:
        choice: str = ""
        确保配置文件存在()
        
        # 交互式模式
        while True:
            choice = ""
            print("\n" + "="*50)
            print("机器狗配置主菜单")
            print("="*50)
            print("1. 修改配置")
            print("2. 安装软件")
            print("3. 群控配置")
            
            main_choice = input("\n请输入选项 (1/2/3): ").strip()
            
            if main_choice == "1":
                while True:
                    print("注意: 自身AP 192.168.234.1，有线 192.168.168.168")
                    机器人IP = input("\n请输入机器狗 IP: ").strip()
                    if not 机器人IP:
                        print("✗ 未提供机器狗 IP")
                        continue
                    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", 机器人IP):
                        print("✗ IP 地址格式无效，请重新输入")
                        continue
                    if 是否禁止IP(机器人IP):
                        print("✗ 此 IP 不允许作为输入")
                        continue
                    break

                while True:
                    本机端口号_str = input("请输入端口号 (默认: 43988): ").strip() or "43988"
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

            robot_ip, robot_port = 读取机器狗配置()
            if not robot_ip or not robot_port:
                print("✗ 请先在主菜单中配置机器狗 IP 和端口号")
                continue
            机器人IP = robot_ip
            本机端口号 = robot_port

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
                    elif install_choice in ["1", "2"]:
                        choice = "install_" + install_choice
                        break
                
                if choice.startswith("install_"):
                    break
                    
            elif main_choice == "3":
                # 群控配置子菜单
                while True:
                    print("\n" + "-"*50)
                    print("群控配置")
                    print("-"*50)
                    print("1. 修改 网络配置（wifi/ap/有线）")
                    print("2. 修改 sdk 配置")
                    print("3. 修改 运控文件 配置")
                    print("4. 重启运控")
                    print("0. 返回主菜单")
                    
                    config_choice = input("\n请输入选项 (0/1/2/3/4): ").strip()
                    
                    if config_choice == "0":
                        break
                    elif config_choice in ["1", "2", "3", "4"]:
                        if config_choice == "1":
                            print("\n请选择网络配置模式:")
                            print("1. AP/有线直连")
                            print("2. WIFI 局域网")
                            net_choice = input("请输入选项 (1/2): ").strip()
                            if net_choice == "1":
                                choice = "config_1_ap"
                                break
                            elif net_choice == "2":
                                choice = "config_1_wifi"
                                break
                            else:
                                print("✗ 无效的选项")
                                continue
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
                                    choice = "config_2_modify"
                                    break
                                elif sdk_choice == "2":
                                    choice = "config_2_view"
                                    break
                                elif sdk_choice == "3":
                                    choice = "config_2_reset"
                                    break
                                else:
                                    print("✗ 无效的选项")
                            if choice:
                                break
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
                                    choice = "config_3_modify"
                                    break
                                elif motion_choice == "2":
                                    choice = "config_3_view"
                                    break
                                elif motion_choice == "3":
                                    choice = "config_3_reset"
                                    break
                                else:
                                    print("✗ 无效的选项")
                            if choice:
                                break
                        else:
                            choice = "config_" + config_choice
                            break
                    else:
                        print("✗ 无效的选项，请重新输入")
                
                if choice.startswith("config_"):
                    break
                    
            else:
                print("✗ 无效的选项，请重新输入")
    
        # 获取SSH认证信息
        用户名 = "firefly"
        密码 = "firefly"
        
        # 创建配置器
        configurator = 机器狗配置器(本机端口号, 机器人IP, 用户名, 密码)
        
        # 连接机器狗
        if not configurator.连接():
            print("\n✗ 无法连接到机器狗，请检查:")
            print("  1. 是否已连接到机器狗的 WIFI")
            print("  2. IP 地址是否正确")
            return
        
        # 执行配置
        if choice == "install_1":
            # 安装 sparkrobot-common
            success = configurator.安装SparkrobotCommon()
        elif choice == "install_2":
            # 安装 robot-server
            success = configurator.安装RobotServer()
        elif choice == "config_1_ap":
            # 修改/查看 网络配置
            success = configurator.配置AP_有线直连模式()
        elif choice == "config_1_wifi":
            success = configurator.配置WIFI局域网模式()
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
            success = configurator.查看修改运控配置(机器人IP)
        elif choice == "config_3_view":
            configurator.查看运控配置()
            success = True
        elif choice == "config_3_reset":
            success = configurator.重置运控配置()
        elif choice == "config_4":
            # 重启运控
            success = configurator.重启运动控制()
        else:
            print(f"✗ 未知的选项: {choice}")
            success = False
        
        if success:
            print("\n" + "="*50)
            print("✓ 配置完成！")
            print("="*50)
        else:
            print("\n" + "="*50)
            print("✗ 配置失败")
            print("="*50)
    
    except (KeyboardInterrupt, EOFError):
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'configurator' in locals():
            configurator.断开连接()


if __name__ == "__main__":
    main()
