"""
机器狗配置脚本
交互式配置菜单，支持软件安装和群控配置
"""

import sys
from scripts.robot.utils import 确保存在包, 是否禁止IP

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
        
        # 交互式模式
        while True:
            print("\n" + "="*50)
            print("机器狗配置主菜单")
            print("="*50)
            print("1. 安装软件")
            print("2. 群控配置")
            
            main_choice = input("\n请输入选项 (1/2): ").strip()
            
            if main_choice == "1":
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
                        机器狗配置器.网络.获取机器狗IP()
                    else:
                        print("✗ 无效的选项，请重新输入")
                
                if choice.startswith("install_"):
                    break
                    
            elif main_choice == "2":
                # 群控配置子菜单
                while True:
                    print("\n" + "-"*50)
                    print("群控配置")
                    print("-"*50)
                    print("1. 修改/查看 网络配置（wifi/ap/有线）")
                    print("2. 修改/查看 sdk 配置")
                    print("3. 修改/查看 运控文件 配置")
                    print("4. 重启运控")
                    print("0. 返回主菜单")
                    
                    config_choice = input("\n请输入选项 (0/1/2/3/4): ").strip()
                    
                    if config_choice == "0":
                        break
                    elif config_choice in ["1", "2", "3", "4"]:
                        # 获取机器狗IP
                        print("\n请选择连接方式:")
                        print("1. AP网络: 192.168.234.1")
                        print("2. 有线网络: 192.168.168.168")
                        print("3. WIFI局域网 (需输入IP)")
                        
                        conn_type = input("请输入选项 (1/2/3): ").strip()
                        
                        if conn_type == "1":
                            机器人IP = "192.168.234.1"
                            choice = "config_" + config_choice
                            break
                        elif conn_type == "2":
                            机器人IP = "192.168.168.168"
                            choice = "config_" + config_choice
                            break
                        elif conn_type == "3":
                            while True:
                                host_in = input("请输入机器狗 IP: ").strip()
                                if 是否禁止IP(host_in):
                                    print("✗ 此 IP 不允许作为输入")
                                    continue
                                机器人IP = host_in
                                choice = "config_" + config_choice
                                break
                            break
                        else:
                            print("✗ 无效的选项")
                    else:
                        print("✗ 无效的选项，请重新输入")
                
                if choice.startswith("config_"):
                    break
                    
            else:
                print("✗ 无效的选项，请重新输入")
    
        # 获取SSH认证信息
        用户名 = "firefly"
        密码 = "firefly"
        
        # 获取端口号（仅在需要时）
        if choice.startswith("install_") or choice == "config_4":
            # 安装软件或仅重启运控时不需要端口
            本机端口号 = None
        else:
            # 交互式输入端口号
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
        
        # 创建配置器
        configurator = 机器狗配置器(本机IP, 本机端口号, 机器人IP, 用户名, 密码)
        
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
        elif choice == "config_1":
            # 修改/查看 网络配置
            success = configurator.配置网络()
        elif choice == "config_2":
            # 修改/查看 sdk 配置
            success = configurator.查看修改SDK配置(本机IP)
        elif choice == "config_3":
            # 修改/查看 运控文件 配置
            success = configurator.查看修改运控配置()
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
