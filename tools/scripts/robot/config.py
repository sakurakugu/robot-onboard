"""机器狗配置器 - 组合各模块功能的主配置器"""

import re
from typing import Optional, Tuple

from .utils import 获取本地IP, 是否禁止IP
from .ssh_manager import SSH管理器
from .network_config import 网络配置管理器
from .sdk_config import SDK配置管理器
from .service_installer import 服务安装管理器


class 机器狗配置器:
    """机器狗配置器 - 组合所有配置功能的主入口"""
    
    def __init__(self, 本机IP: int, 机器人IP: str, 用户名: str = "firefly", 密码: str = "firefly"):
        self.机器人IP = 机器人IP
        self.用户名 = 用户名
        self.密码 = 密码
        self.本机IP = 本机IP
        self.auto_confirm = False  # 是否自动确认（用于命令行模式）
        
        # 创建各功能管理器
        self.ssh = SSH管理器(机器人IP, 用户名, 密码)
        self.网络 = 网络配置管理器(self.ssh)
        self.sdk = SDK配置管理器(self.ssh)
        self.服务 = 服务安装管理器(self.ssh)
    
    # ========== SSH 相关方法（委托给 ssh 管理器）==========
    def 连接(self) -> bool:
        """连接到机器狗"""
        return self.ssh.连接()
    
    def 断开连接(self):
        """断开连接"""
        self.ssh.断开连接()
    
    def 执行命令(self, command: str, use_sudo: bool = False) -> Tuple[bool, str, str]:
        """执行远程命令"""
        return self.ssh.执行命令(command, use_sudo)
    
    # ========== SDK 相关方法（委托给 sdk 管理器）==========
    def 修改SDK配置(self, target_ip: str, target_port: int) -> bool:
        """修改 SDK 配置"""
        return self.sdk.修改SDK配置(target_ip, target_port)
    
    def 修改运控启动脚本(self, sdk_client_ip: Optional[str] = None) -> bool:
        """修改运控启动脚本"""
        return self.sdk.修改运控启动脚本(sdk_client_ip)
    
    def 重启运动控制(self) -> bool:
        """重启运控"""
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
    
    # ========== 服务安装相关方法（委托给服务管理器）==========
    def 安装SparkRobotCommon(self) -> bool:
        """安装 SparkRobot Common"""
        return self.服务.安装SparkRobotCommon()
    
    def 安装RobotServer(self) -> bool:
        """安装 Robot Server"""
        return self.服务.安装RobotServer()
    
    # ========== 用户交互方法 ==========
    def 获取用户输入的IP(self, prompt_prefix: str = "本机", show_network_info: bool = True) -> Optional[str]:
        """获取用户输入的IP地址，支持自动检测和查看网络信息"""
        current_ip = 获取本地IP()
        
        while True:
            if current_ip:
                print(f"检测到当前 IP: {current_ip}")
                if show_network_info:
                    ip = input(f"按回车使用此IP作为{prompt_prefix}IP，或输入新IP，输入'ip'查看网络信息: ").strip()
                else:
                    ip = input(f"按回车使用此IP作为{prompt_prefix}IP，或输入新IP: ").strip()
            else:
                print("未能自动检测到 IP 地址")
                if show_network_info:
                    ip = input(f"请输入{prompt_prefix}IP，或输入'ip'查看网络信息: ").strip()
                else:
                    ip = input(f"请输入{prompt_prefix}IP: ").strip()
            
            if show_network_info and ip.lower() == 'ip':
                print("\n" + "-"*50)
                success, output, _ = self.ssh.执行命令("ip addr")
                if success:
                    print(output)
                else:
                    print("✗ 无法获取网络信息")
                print("-"*50 + "\n")
                continue
            elif ip == "" and current_ip:
                return current_ip
            elif ip:
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                    if 是否禁止IP(ip):
                        print("✗ 此 IP 不允许作为输入，请更换")
                        continue
                    return ip
                else:
                    print("✗ IP 地址格式无效，请重新输入")
            else:
                print(f"✗ 未提供{prompt_prefix}IP")
                return None
    
    # ========== 配置模式方法 ==========
    def 配置AP_有线直连模式(self) -> bool:
        """配置 AP/有线直连模式（交互式）"""
        print("\n" + "="*50)
        print("AP/有线直连模式配置")
        print("="*50)
        
        local_ip = self.获取用户输入的IP("本机", show_network_info=True)
        if not local_ip:
            return False
        
        if not self.sdk.修改SDK配置(local_ip, 43988):
            return False
        
        if not self.sdk.修改运控启动脚本(None):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()

    def 配置AP_有线直连模式_自动(self, local_ip: str) -> bool:
        """配置 AP/有线直连模式（命令行自动模式）"""
        print("\n" + "="*50)
        print("AP/有线直连模式配置（自动）")
        print("="*50)
        print(f"本机 IP: {local_ip}")
        
        if not self.sdk.修改SDK配置(local_ip, 43988):
            return False
        
        if not self.sdk.修改运控启动脚本(None):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
    
    def 仅修改SDK配置并重启(self) -> bool:
        """仅修改 SDK 配置并重启运控（交互式）"""
        print("\n" + "="*50)
        print("修改 SDK 配置并重启运控")
        print("="*50)
        
        local_ip = self.获取用户输入的IP("本机", show_network_info=True)
        if not local_ip:
            return False
        
        if not self.sdk.修改SDK配置(local_ip, 43988):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
    
    def 仅修改SDK配置并重启_自动(self, local_ip: str) -> bool:
        """仅修改 SDK 配置并重启运控（命令行自动模式）"""
        print("\n" + "="*50)
        print("修改 SDK 配置并重启运控（自动）")
        print("="*50)
        print(f"本机 IP: {local_ip}")
        
        if not self.sdk.修改SDK配置(local_ip, self.本机IP):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
    
    def 配置WIFI局域网模式(self) -> bool:
        """配置 WIFI 局域网模式（交互式）"""
        print("\n" + "="*50)
        print("WIFI 局域网模式配置")
        print("="*50)
        
        # 连接 WIFI - 支持重试
        max_retries = 3
        for attempt in range(max_retries):
            ssid = input("请输入 WIFI 名称: ").strip()
            密码 = input("请输入 WIFI 密码: ").strip()
            
            if not ssid or not 密码:
                print("✗ WIFI 信息不完整")
                if attempt < max_retries - 1:
                    retry = input("是否重新输入？(Y/n): ").strip().lower()
                    if retry == 'n':
                        return False
                    continue
                else:
                    return False
            
            if self.网络.连接Wifi(ssid, 密码):
                break
            else:
                if attempt < max_retries - 1:
                    print(f"\n连接失败，还可以尝试 {max_retries - attempt - 1} 次")
                    retry = input("是否重新输入WIFI信息？(Y/n): ").strip().lower()
                    if retry == 'n':
                        return False
                else:
                    print("\n✗ 已达到最大重试次数")
                    return False
        
        # 获取机器狗在 WIFI 网络中的 IP 和 MAC 地址
        robot_ip, robot_mac = self.网络.获取机器人WIFI_IP()
        if not robot_ip:
            print("\n未能自动获取机器狗 WIFI IP")
            if robot_mac:
                print(f"提示: 可以在路由器中通过 MAC 地址 {robot_mac} 查找对应的 IP")
            robot_ip = input("请手动输入机器狗 WIFI IP: ").strip()
            if not robot_ip:
                print("✗ 未提供机器狗 WIFI IP")
                return False
        
        print("\n重要信息：")
        print(f"机器狗 WIFI IP: {robot_ip}")
        if robot_mac:
            print(f"机器狗 MAC 地址: {robot_mac}")
        print("后续请使用此 IP 通过 SSH 连接机器狗")
        
        # 获取本机 IP（用于 SDK 配置）
        print()
        local_ip = self.获取用户输入的IP("本机在 WIFI 网络中的", show_network_info=False)
        if not local_ip:
            return False
        
        if not self.sdk.修改SDK配置(local_ip, 43988):
            return False
        
        if not self.sdk.修改运控启动脚本(robot_ip):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
    
    def 配置WIFI局域网模式_自动(self, ssid: str, 密码: str, local_ip: str) -> bool:
        """配置 WIFI 局域网模式（命令行自动模式）"""
        print("\n" + "="*50)
        print("WIFI 局域网模式配置（自动）")
        print("="*50)
        print(f"WIFI 名称: {ssid}")
        print(f"本机 IP: {local_ip}")
        
        if not self.网络.连接Wifi(ssid, 密码):
            return False
        
        robot_ip, robot_mac = self.网络.获取机器人WIFI_IP()
        if not robot_ip:
            print("\n✗ 未能自动获取机器狗 WIFI IP")
            if robot_mac:
                print(f"提示: 可以在路由器中通过 MAC 地址 {robot_mac} 查找对应的 IP")
            return False
        
        print("\n重要信息：")
        print(f"机器狗 WIFI IP: {robot_ip}")
        if robot_mac:
            print(f"机器狗 MAC 地址: {robot_mac}")
        print("后续请使用此 IP 通过 SSH 连接机器狗")
        
        if not self.sdk.修改SDK配置(local_ip, 43988):
            return False
        
        if not self.sdk.修改运控启动脚本(robot_ip):
            return False
        
        self.sdk.auto_confirm = self.auto_confirm
        return self.sdk.重启运动控制()
