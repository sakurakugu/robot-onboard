#!/usr/bin/env python3
"""
机器狗自动配置脚本
支持 AP/有线直连模式和 WIFI 局域网模式的自动配置
"""

import subprocess
import sys
import time
import re
import socket
import argparse
from typing import Optional, Tuple

# 禁止输入的 IP 列表/前缀
BANNED_IPS = {"127.0.0.1", "192.168.234.1", "192.168.168.168"}
# BANNED_PREFIXES = ("192.168.168",)

def 是否禁止IP(ip: str) -> bool:
    if ip in BANNED_IPS:
        return True
    # for pref in BANNED_PREFIXES:
    #     if ip.startswith(pref + ".") or ip == pref:
    #         return True
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
        
确保存在包("paramiko")
import paramiko

确保存在包("ruamel.yaml")
from ruamel.yaml import YAML


def get_local_udp_ip():
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


class RobotConfigurator:
    """机器狗配置器"""
    
    def __init__(self, target_port: int, host: str, username: str = "firefly", password: str = "firefly", ):
        self.host = host
        self.username = username
        self.password = password
        self.target_port = target_port
        self.client: Optional[paramiko.SSHClient] = None
        self.auto_confirm = False  # 是否自动确认（用于命令行模式）
    
    def 获取用户输入的IP(self, prompt_prefix: str = "本机", show_network_info: bool = True) -> Optional[str]:
        """获取用户输入的IP地址，支持自动检测和查看网络信息
        
        Args:
            prompt_prefix: 提示前缀，如"本机"、"target"
            show_network_info: 是否支持输入'ip'查看网络信息
        
        Returns:
            IP地址字符串，失败返回None
        """
        current_ip = get_local_udp_ip()
        
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
                # 显示网络信息
                print("\n" + "-"*50)
                success, output, _ = self.执行命令("ip addr")
                if success:
                    print(output)
                else:
                    print("✗ 无法获取网络信息")
                print("-"*50 + "\n")
                continue
            elif ip == "" and current_ip:
                return current_ip
            elif ip:
                # 验证IP格式
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
    
    def 写入配置文件(self, content: str, target_path: str, description: str = "配置文件") -> bool:
        """将内容写入配置文件（通过临时文件）
        
        Args:
            content: 文件内容
            target_path: 目标文件路径
            description: 文件描述，用于错误提示
        
        Returns:
            成功返回True，失败返回False
        """
        temp_file = "/tmp/" + target_path.split("/")[-1]
        
        # 写入临时文件
        write_cmd = f"cat > {temp_file} << 'EOF'\n{content}\nEOF"
        success, _, error = self.执行命令(write_cmd)
        if not success:
            print(f"✗ 写入临时文件失败: {error}")
            return False
        
        # 复制到目标位置
        success, _, error = self.执行命令(f"cp {temp_file} {target_path}", use_sudo=True)
        if not success:
            print(f"✗ 复制{description}失败: {error}")
            return False
        
        return True
        
    def 连接(self) -> bool:
        """连接到机器狗"""
        try:
            print(f"正在连接机器狗 {self.host}...")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                timeout=10
            )
            print("✓ 成功连接到机器狗")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def 断开连接(self):
        if self.client:
            self.client.close()
            print("已断开连接")
    
    def 执行命令(self, command: str, use_sudo: bool = False) -> Tuple[bool, str, str]:
        """执行远程命令"""
        if not self.client:
            return False, "", "未连接到机器狗"
        
        try:
            if use_sudo:
                # 使用 sudo 并提供密码
                command = f"echo {self.password} | sudo -S {command}"
            
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            out = stdout.read().decode('utf-8')
            err = stderr.read().decode('utf-8')
            
            return exit_status == 0, out, err
        except Exception as e:
            return False, "", str(e)

    def get_local_ip(self, interface: str = "wlan0") -> Optional[str]:
        """
          获取本机在机器狗网络中的 IP 地址
          (WSL没用wlan0，要修改成对应的接口名称)
        """
        print(f"正在获取本机在 {interface} 上的 IP 地址...")
        success, output, error = self.执行命令("ip addr show")
        
        if not success:
            print(f"✗ 获取 IP 失败: {error}")
            return None
        
        # 查找指定接口的 IP 地址
        pattern = rf"{interface}:.*?inet (\d+\.\d+\.\d+\.\d+)"
        match = re.search(pattern, output, re.DOTALL)
        
        if match:
            ip = match.group(1)
            print(f"✓ 本机 IP: {ip}")
            return ip
        
        print(f"✗ 未找到 {interface} 接口的 IP 地址")
        return None
    
    def get_robot_wifi_ip(self, interface: str = "wlan0") -> Tuple[Optional[str], Optional[str]]:
        """获取机器狗在 WIFI 网络中的 IP 地址和 MAC 地址"""
        print(f"正在获取机器狗在 {interface} 上的网络信息...")
        success, output, error = self.执行命令(f"ip addr show {interface}")
        
        if not success:
            print(f"✗ 获取网络信息失败: {error}")
            return None, None
        
        # 查找 IP 地址
        ip_pattern = r"inet (\d+\.\d+\.\d+\.\d+)"
        ip_match = re.search(ip_pattern, output)
        
        # 查找 MAC 地址
        mac_pattern = r"link/ether ([0-9a-f:]{17})"
        mac_match = re.search(mac_pattern, output)
        
        ip = ip_match.group(1) if ip_match else None
        mac = mac_match.group(1) if mac_match else None
        
        if ip:
            print(f"✓ 机器狗 WIFI IP: {ip}")
        else:
            print("✗ 未找到机器狗的 WIFI IP 地址")
            
        if mac:
            print(f"✓ 机器狗 MAC 地址: {mac}")
        else:
            print("⚠️  未找到机器狗的 MAC 地址")
        
        return ip, mac
    
    def 修改SDK配置(self, target_ip: str, target_port: int = None) -> bool:
        """修改 SDK 配置文件"""
        print("正在修改 SDK 配置文件...")
        config_path = "/opt/export/config/sdk_config.yaml"
        
        if target_port is None:
            target_port = self.target_port
        
        # 读取配置文件
        success, content, error = self.执行命令(f"cat {config_path}", use_sudo=True)
        if not success:
            print(f"✗ 读取配置文件失败: {error}")
            return False
        
        # 使用 ruamel.yaml 解析与更新配置
        try:
            import io
            yaml = YAML()
            yaml.preserve_quotes = True  # 保留引号
            yaml.default_flow_style = False  # 使用块风格
            
            data_stream = io.StringIO(content)
            data = yaml.load(data_stream)
            
            if data is None:
                data = {}
            
            # 更新配置
            data['target_ip'] = str(target_ip)
            data['target_port'] = int(target_port)
            
            # 生成新的 YAML 内容
            out_stream = io.StringIO()
            yaml.dump(data, out_stream)
            modified_content = out_stream.getvalue()
        except Exception as e:
            print(f"✗ YAML 解析/生成失败: {e}")
            return False
        
        if not self.写入配置文件(modified_content, config_path, "SDK配置文件"):
            return False
        
        print(f"✓ SDK 配置文件已更新 (target_ip: {target_ip}, target_port: {target_port})")
        return True
    
    def 连接Wifi(self, ssid: str, password: str) -> bool:
        """连接 WIFI 网络"""
        print(f"正在连接 WIFI: {ssid}...")
        
        # 连接 WIFI
        cmd = f"nmcli device wifi connect '{ssid}' password '{password}' ifname wlan0"
        success, output, error = self.执行命令(cmd, use_sudo=True)
        
        if not success:
            print(f"✗ 连接 WIFI 失败: {error}")
            return False
        
        print("✓ 成功连接 WIFI")
        
        # 关闭网络清除服务
        print("正在配置网络服务...")
        self.执行命令("systemctl stop networkmanager-cleanup.service", use_sudo=True)
        self.执行命令("systemctl disable networkmanager-cleanup.service", use_sudo=True)
        
        # 开启自动连接
        cmd = f"nmcli connection modify '{ssid}' connection.autoconnect yes"
        self.执行命令(cmd, use_sudo=True)
        
        print("✓ WIFI 配置完成")
        time.sleep(2)
        
        return True
    
    def 修改运控启动脚本(self, sdk_client_ip: Optional[str] = None) -> bool:
        """修改运控启动脚本"""
        print("正在修改运控启动脚本...")
        script_path = "/opt/app_launch/start_motion_control.sh"
        
        # 读取脚本
        success, content, error = self.执行命令(f"cat {script_path}", use_sudo=True)
        if not success:
            print(f"✗ 读取脚本失败: {error}")
            return False
        
        # 检查是否已存在 SDK_CLIENT_IP 配置
        if "SDK_CLIENT_IP" in content:
            # 移除旧的配置
            content = re.sub(r"\nexport SDK_CLIENT_IP=.*\n", "\n", content)
        
        if sdk_client_ip:
            # 在 ROBOT_TYPE 后添加 SDK_CLIENT_IP
            content = re.sub(
                r"(export ROBOT_TYPE=\w+)",
                f"\\1\nexport SDK_CLIENT_IP='{sdk_client_ip}'",
                content
            )
            print(f"✓ 已设置 SDK_CLIENT_IP={sdk_client_ip}")
        else:
            print("✓ AP/有线直连模式，未设置 SDK_CLIENT_IP")
        
        if not self.写入配置文件(content, script_path, "运控启动脚本"):
            return False
        
        print("✓ 运控启动脚本已更新")
        return True
    
    def 重启运动控制(self) -> bool:
        """重启运控"""
        print("\n⚠️  准备重启运控...")
        print("⚠️  请确保机器狗已经卧倒，否则会急停！")
        
        if self.auto_confirm:
            print("自动确认模式：假定机器狗已卧倒")
            response = "yes"
        else:
            response = input("确认机器狗已卧倒？(Yes/no): ").strip().lower() or "yes"
            
        if response != "yes":
            print("取消重启运控")
            return False
        
        print("正在重启运控...")
        success, output, error = self.执行命令("robot-launch restart 4", use_sudo=True)
        
        if success:
            print("✓ 运控重启成功")
            return True
        else:
            print(f"✗ 运控重启失败: {error}")
            return False
    
    def 配置AP_有线直连模式(self) -> bool:
        """配置 AP/有线直连模式"""
        print("\n" + "="*50)
        print("AP/有线直连模式配置")
        print("="*50)
        
        # 获取本机 IP（在机器狗的热点网络中）
        local_ip = self.获取用户输入的IP("本机", show_network_info=True)
        if not local_ip:
            return False
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip):
            return False
        
        # 修改运控脚本（AP/有线 模式不需要 SDK_CLIENT_IP）
        if not self.修改运控启动脚本(None):
            return False
        
        # 重启运控
        return self.重启运动控制()
    
    def 仅修改SDK配置并重启(self) -> bool:
        """仅修改 SDK 配置并重启运控"""
        print("\n" + "="*50)
        print("修改 SDK 配置并重启运控")
        print("="*50)
        
        # 获取本机 IP（用于 SDK 配置）
        local_ip = self.获取用户输入的IP("本机", show_network_info=True)
        if not local_ip:
            return False
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip, self.target_port):
            return False
        
        # 重启运控
        return self.重启运动控制()
    
    def 配置AP_有线直连模式_自动(self, local_ip: str) -> bool:
        """配置 AP/有线直连模式（命令行自动模式）"""
        print("\n" + "="*50)
        print("AP/有线直连模式配置（自动）")
        print("="*50)
        print(f"本机 IP: {local_ip}")
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip):
            return False
        
        # 修改运控脚本（AP/有线 模式不需要 SDK_CLIENT_IP）
        if not self.修改运控启动脚本(None):
            return False
        
        # 重启运控
        return self.重启运动控制()
    
    def 仅修改SDK配置并重启_自动(self, local_ip: str) -> bool:
        """仅修改 SDK 配置并重启运控（命令行自动模式）"""
        print("\n" + "="*50)
        print("修改 SDK 配置并重启运控（自动）")
        print("="*50)
        print(f"本机 IP: {local_ip}")
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip, self.target_port):
            return False
        
        # 重启运控
        return self.重启运动控制()
    
    def 配置WIFI局域网模式_自动(self, ssid: str, password: str, local_ip: str) -> bool:
        """配置 WIFI 局域网模式（命令行自动模式）"""
        print("\n" + "="*50)
        print("WIFI 局域网模式配置（自动）")
        print("="*50)
        print(f"WIFI 名称: {ssid}")
        print(f"本机 IP: {local_ip}")
        
        # 连接 WIFI
        if not self.连接Wifi(ssid, password):
            return False
        
        # 获取机器狗在 WIFI 网络中的 IP 和 MAC 地址
        robot_ip, robot_mac = self.get_robot_wifi_ip()
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
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip):
            return False
        
        # 修改运控脚本（WIFI 模式需要设置 SDK_CLIENT_IP）
        if not self.修改运控启动脚本(robot_ip):
            return False
        
        # 重启运控
        return self.重启运动控制()
    
    def 配置WIFI局域网模式(self) -> bool:
        """配置 WIFI 局域网模式"""
        print("\n" + "="*50)
        print("WIFI 局域网模式配置")
        print("="*50)
        
        # 连接 WIFI - 支持重试
        max_retries = 3
        for attempt in range(max_retries):
            ssid = input("请输入 WIFI 名称: ").strip()
            password = input("请输入 WIFI 密码: ").strip()
            
            if not ssid or not password:
                print("✗ WIFI 信息不完整")
                if attempt < max_retries - 1:
                    retry = input("是否重新输入？(Y/n): ").strip().lower()
                    if retry == 'n':
                        return False
                    continue
                else:
                    return False
            
            if self.连接Wifi(ssid, password):
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
        robot_ip, robot_mac = self.get_robot_wifi_ip()
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
        print()  # 空行
        local_ip = self.获取用户输入的IP("本机在 WIFI 网络中的", show_network_info=False)
        if not local_ip:
            return False
        
        # 修改 SDK 配置
        if not self.修改SDK配置(local_ip):
            return False
        
        # 修改运控脚本（WIFI 模式需要设置 SDK_CLIENT_IP）
        if not self.修改运控启动脚本(robot_ip):
            return False
        
        # 重启运控
        return self.重启运动控制()


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='机器狗自动配置脚本 - 支持 AP 直连模式和 WIFI 局域网模式的自动配置',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 交互式配置（默认模式）
  python 配置机器狗.py
  
  # AP/有线直连模式 - 自动配置
  python 配置机器狗.py --mode ap --ap_link ap --local_ip 192.168.234.100 --port 10001
  python 配置机器狗.py --mode ap --ap_link wired --local_ip 192.168.168.100 --port 10001
  
  # WIFI 局域网模式 - 自动配置
  python 配置机器狗.py --mode wifi --wifi_name MyWiFi --wifi_password 12345678 \\
      --local_ip 192.168.1.100 --port 10001
  
  # 仅修改 SDK 配置并重启
  python 配置机器狗.py --mode sdk --local_ip 192.168.1.100 --port 10001 \\
      --robot_ip 192.168.1.50
  
  # 指定机器狗 IP（用于 WIFI 模式）
  python 配置机器狗.py --mode wifi --robot_ip 192.168.1.50 \\
      --wifi_name MyWiFi --wifi_password 12345678
 
  # 管理 AP 密码（示例：查看/修改/删除/恢复）
  python 配置机器狗.py --mode ap --ap_link ap --nm_ap_action show --nm_ssid BETEC_5G
  python 配置机器狗.py --mode ap --ap_link ap --nm_ap_action change --nm_ssid BETEC_5G --nm_psk 新密码
  python 配置机器狗.py --mode ap --ap_link ap --nm_ap_action delete --nm_ssid BETEC_5G
  python 配置机器狗.py --mode ap --ap_link ap --nm_ap_action restore --nm_ssid BETEC_5G --nm_psk betec12345@
 
  # 自连模式（IP 127.0.0.1，端口 43988）
  python 配置机器狗.py --mode self

配置模式说明:
  ap   - AP/有线直连模式（机器狗作为热点）
  wifi - WIFI 局域网模式（机器狗连接到 WIFI）
  sdk  - 仅修改 SDK 配置并重启运控
  self - 自连模式（IP 127.0.0.1，端口 43988）
        '''
    )
    
    # 基本参数
    parser.add_argument('--mode', 
                       choices=['ap', 'wifi', 'sdk', 'self'],
                       help='配置模式: ap=AP/有线直连, wifi=WIFI局域网, sdk=仅修改SDK配置')
    parser.add_argument('--ap_link',
                       choices=['ap', 'wired'],
                       help='AP 模式连接类型: ap=热点, wired=有线直连（仅在 --mode ap 时使用）')
    
    parser.add_argument('--robot_ip',
                       help='机器狗 IP 地址 (默认: 192.168.234.1)')
    
    parser.add_argument('--local_ip',
                       help='本机 IP 地址（用于 SDK 配置）')
    
    parser.add_argument('--port',
                       type=int,
                       help='机器狗端口号（1-65535）')
    
    # WIFI 模式参数
    parser.add_argument('--wifi_name',
                       help='WIFI 名称（WIFI 模式必需）')
    
    parser.add_argument('--wifi_password',
                       help='WIFI 密码（WIFI 模式必需）')
    
    # 认证参数
    parser.add_argument('--username',
                       default='firefly',
                       help='SSH 用户名 (默认: firefly)')
    
    parser.add_argument('--password',
                       default='firefly',
                       help='SSH 密码 (默认: firefly)')
    
    # 交互模式控制
    parser.add_argument('--no-confirm',
                       action='store_true',
                       help='跳过重启运控的确认提示（自动确认）')
    
    # AP 密码管理
    parser.add_argument('--nm_ap_action',
                       choices=['show', 'change', 'delete', 'restore'],
                       help='AP 密码管理动作: show/change/delete/restore')
    parser.add_argument('--nm_ssid',
                       help='AP 连接名称（如 BETEC_5G）')
    parser.add_argument('--nm_psk',
                       help='AP 新密码（用于 change/restore）')
    
    return parser.parse_args()


def validate_arguments(args):
    """验证命令行参数的有效性"""
    errors = []
    
    # 如果指定了模式，则需要某些必需参数
    if args.mode:
        if args.mode in ['ap', 'sdk']:
            if not args.local_ip:
                errors.append("--local_ip 是必需参数")
            if not args.port:
                errors.append("--port 是必需参数")
            if args.mode == 'ap' and not args.robot_ip and not args.ap_link:
                errors.append("--mode ap 时未指定 --robot_ip 或 --ap_link")
        
        if args.mode == 'wifi':
            if not args.wifi_name:
                errors.append("WIFI 模式需要 --wifi_name 参数")
            if not args.wifi_password:
                errors.append("WIFI 模式需要 --wifi_password 参数")
            if not args.local_ip:
                errors.append("WIFI 模式需要 --local_ip 参数")
            if not args.port:
                errors.append("--port 是必需参数")
        
        if args.mode == 'self':
            pass
    
    # AP 密码管理参数组合校验
    if args.nm_ap_action:
        if not args.nm_ssid:
            errors.append("AP 密码管理需要提供 --nm_ssid")
        if args.nm_ap_action in ('change', 'restore') and not args.nm_psk:
            errors.append(f"{args.nm_ap_action} 需要提供 --nm_psk")
    
    # 验证 IP 地址格式
    ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if args.local_ip and not ip_pattern.match(args.local_ip):
        errors.append(f"--local_ip 格式无效: {args.local_ip}")
    if args.robot_ip and not ip_pattern.match(args.robot_ip):
        errors.append(f"--robot_ip 格式无效: {args.robot_ip}")
    if args.local_ip and 是否禁止IP(args.local_ip):
        errors.append(f"--local_ip 不允许使用此 IP: {args.local_ip}")
    if args.robot_ip and 是否禁止IP(args.robot_ip):
        errors.append(f"--robot_ip 不允许使用此 IP: {args.robot_ip}")
    
    # 验证端口号
    if args.port:
        if args.port < 1 or args.port > 65535:
            errors.append(f"--port 必须在 1-65535 之间: {args.port}")
    
    if errors:
        print("✗ 参数验证失败:")
        for error in errors:
            print(f"  - {error}")
        print("\n使用 --help 查看使用说明")
        sys.exit(1)


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 如果提供了命令行参数，验证其有效性
    if args.mode:
        validate_arguments(args)
    
    print("="*50)
    print("机器狗自动配置脚本")
    print("="*50)
    
    try:
        # 确定配置模式
        if args.mode:
            choice = {'ap': '1', 'wifi': '2', 'sdk': '3', 'self': '4'}[args.mode]
            if args.robot_ip:
                host = args.robot_ip
            else:
                if args.mode == 'ap':
                    if args.ap_link == 'wired':
                        host = "192.168.168.168"
                    else:
                        host = "192.168.234.1"
                else:
                    host = "192.168.234.1"
            print(f"\n命令行模式: {args.mode.upper()}")
            print(f"机器狗 IP: {host}")
        else:
            # 交互式模式
            while True:
                print("\n" + "-"*25)
                print("请选择配置模式:")
                print("1. AP/有线直连模式")
                print("2. WIFI 局域网模式")
                print("3. 仅修改 SDK 配置并重启运控")
                print("4. 自连模式（IP 127.0.0.1，端口 43988）")
                
                choice = input("\n请输入选项 (1/2/3/4): ").strip()
                
                if choice == "1":
                    while True:
                        print("请输入数字选择网络")
                        print("1. AP网络: 192.168.234.1")
                        print("2. 有线网络: 192.168.168.168")
                        flag = input("\n请输入选项 (1/2): ").strip()
                        if flag == "1":
                            host = "192.168.234.1"
                            break
                        elif flag == "2":
                            host = "192.168.168.168"
                            break
                        else:
                            print("✗ 无效的选项，请重新输入")
                            continue
                    break
                elif choice == "2":
                    print("\n注意: 需要先通过 AP/有线直连模式连接机器狗来配置 WIFI")
                    while True:
                        host_in = input("请输入机器狗 IP (默认: 192.168.234.1): ").strip() or "192.168.234.1"
                        if 是否禁止IP(host_in):
                            print("✗ 此 IP 不允许作为输入，请更换")
                            continue
                        host = host_in
                        break
                    break
                elif choice == "3":
                    while True:
                        host_in = input("请输入机器狗 IP (默认: 192.168.234.1): ").strip() or "192.168.234.1"
                        if 是否禁止IP(host_in):
                            print("✗ 此 IP 不允许作为输入，请更换")
                            continue
                        host = host_in
                        break
                    break
                elif choice == "4":
                    while True:
                        host_in = input("请输入机器狗 IP (默认: 192.168.234.1): ").strip() or "192.168.234.1"
                        if 是否禁止IP(host_in):
                            print("✗ 此 IP 不允许作为输入，请更换")
                            continue
                        host = host_in
                        break
                    break
                else:
                    print("✗ 无效的选项，请重新输入")
        
        # 获取用户名和密码
        username = args.username
        password = args.password
        
        # 获取端口号
        if args.mode == 'self' or choice == "4":
            target_port = 43988
            print(f"端口号: {target_port}")
        elif args.port:
            target_port = args.port
            print(f"端口号: {target_port}")
        else:
            # 交互式输入端口号
            while True:
                target_port_str = input("请输入端口号: ").strip()
                if not target_port_str:
                    print("✗ 端口号不能为空")
                    continue
                try:
                    target_port = int(target_port_str)
                    if 1 <= target_port <= 65535:
                        break
                    else:
                        print("✗ 端口号必须在 1-65535 之间")
                except ValueError:
                    print("✗ 请输入有效的数字")
        
        # 创建配置器
        configurator = RobotConfigurator(target_port, host, username, password)
        
        # 如果使用命令行模式，设置跳过确认
        if args.mode and args.no_confirm:
            configurator.auto_confirm = True
        
        # 连接机器狗
        if not configurator.连接():
            print("\n✗ 无法连接到机器狗，请检查:")
            print("  1. 是否已连接到机器狗的 WIFI")
            print("  2. IP 地址是否正确")
            return
        
        # 如果指定了 AP 密码管理动作，优先执行并退出
        if args.nm_ap_action:
            action = args.nm_ap_action
            ssid = args.nm_ssid
            psk = args.nm_psk
            if action == 'show':
                ok, out, err = configurator.执行命令(f"nmcli -s -g 802-11-wireless-security.psk connection show '{ssid}'", use_sudo=True)
                if ok and out.strip() and out.strip() != "<hidden>":
                    print(f"AP 密码: {out.strip()}")
                else:
                    ok2, out2, err2 = configurator.执行命令(f"grep -r \"psk=\" /etc/NetworkManager/system-connections/'{ssid}'.nmconnection", use_sudo=True)
                    if ok2 and out2.strip():
                        print(out2.strip())
                    else:
                        print("未能读取到密码")
                        if err or err2:
                            print(err or err2)
                configurator.断开连接()
                return
            elif action == 'change':
                cmds = [
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.key-mgmt wpa-psk",
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.psk '{psk}'",
                    f"nmcli connection up '{ssid}'"
                ]
                all_ok = True
                for c in cmds:
                    ok, _, err = configurator.执行命令(c, use_sudo=True)
                    if not ok:
                        all_ok = False
                        print(err)
                print("✓ AP 密码已更改" if all_ok else "✗ 更改 AP 密码时出现错误")
                configurator.断开连接()
                return
            elif action == 'delete':
                cmds = [
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.psk ''",
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.key-mgmt none",
                    f"nmcli connection up '{ssid}'"
                ]
                all_ok = True
                for c in cmds:
                    ok, _, err = configurator.执行命令(c, use_sudo=True)
                    if not ok:
                        all_ok = False
                        print(err)
                print("✓ AP 密码已删除/设置为开放网络" if all_ok else "✗ 删除 AP 密码时出现错误")
                configurator.断开连接()
                return
            elif action == 'restore':
                default_psk = psk or "betec12345@"
                cmds = [
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.key-mgmt wpa-psk",
                    f"nmcli connection modify '{ssid}' 802-11-wireless-security.psk '{default_psk}'",
                    f"nmcli connection up '{ssid}'"
                ]
                all_ok = True
                for c in cmds:
                    ok, _, err = configurator.执行命令(c, use_sudo=True)
                    if not ok:
                        all_ok = False
                        print(err)
                print("✓ AP 密码已恢复" if all_ok else "✗ 恢复 AP 密码时出现错误")
                configurator.断开连接()
                return
        
        # 执行配置
        if choice == "1":
            if args.mode and args.local_ip:
                # 命令行模式 - AP/有线直连
                success = configurator.配置AP_有线直连模式_自动(args.local_ip)
            else:
                # 交互式模式
                success = configurator.配置AP_有线直连模式()
        elif choice == "2":
            if args.mode and args.wifi_name and args.wifi_password and args.local_ip:
                # 命令行模式 - WIFI 局域网
                success = configurator.配置WIFI局域网模式_自动(
                    args.wifi_name, 
                    args.wifi_password, 
                    args.local_ip
                )
            else:
                # 交互式模式
                success = configurator.配置WIFI局域网模式()
        elif choice == "3":
            if args.mode and args.local_ip:
                # 命令行模式 - 仅修改 SDK
                success = configurator.仅修改SDK配置并重启_自动(args.local_ip)
            else:
                # 交互式模式
                success = configurator.仅修改SDK配置并重启()
        else:
            target_ip = "127.0.0.1"
            ok1 = configurator.修改SDK配置(target_ip, 43988)
            ok2 = configurator.修改运控启动脚本(target_ip)
            success = ok1 and ok2 and configurator.重启运动控制()
        
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
