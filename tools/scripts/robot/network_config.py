"""网络配置模块 - 处理机器狗的网络连接和 IP 地址管理"""

import re
import time
from typing import Optional, Tuple
from .utils import 是否禁止IP


class 网络配置管理器:
    """网络配置管理器 - 处理 WIFI 连接、IP 获取等网络操作"""
    
    def __init__(self, ssh管理器):
        self.ssh = ssh管理器
    
    def 获取本地IP(self, interface: str = "wlan0") -> Optional[str]:
        """获取本机在机器狗网络中的 IP 地址
        
        Args:
            interface: 网络接口名称，默认 wlan0
            
        Returns:
            IP地址字符串，失败返回None
        """
        print(f"正在获取本机在 {interface} 上的 IP 地址...")
        success, output, error = self.ssh.执行命令("ip addr show")
        
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
    
    def 获取机器人WIFI_IP(self, interface: str = "wlan0") -> Tuple[Optional[str], Optional[str]]:
        """获取机器狗在 WIFI 网络中的 IP 地址和 MAC 地址
        
        Args:
            interface: 网络接口名称，默认 wlan0
            
        Returns:
            (IP地址, MAC地址) 元组，失败则对应项为None
        """
        print(f"正在获取机器狗在 {interface} 上的网络信息...")
        success, output, error = self.ssh.执行命令(f"ip addr show {interface}")
        
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
    
    def 获取当前连接的WIFI信息(self) -> Tuple[Optional[str], Optional[str]]:
        """获取当前连接的 WIFI SSID 和 IP
        
        Returns:
            (SSID, IP) 元组
        """
        print("正在获取当前 WIFI 信息...")
        
        # 获取 SSID
        cmd_ssid = "nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2"
        success_ssid, output_ssid, _ = self.ssh.执行命令(cmd_ssid)
        ssid = output_ssid.strip() if success_ssid and output_ssid.strip() else None
        
        # 获取 IP
        ip, _ = self.获取机器人WIFI_IP()
        
        if ssid:
            print(f"✓ 当前连接 WIFI: {ssid}")
        else:
            print("✗ 未连接到任何 WIFI")
            
        return ssid, ip

    def 连接Wifi(self, ssid: str, 密码: str) -> bool:
        """连接到指定的 WIFI 网络
        
        Args:
            ssid: WIFI 名称
            密码: WIFI 密码
            
        Returns:
            成功返回True，失败返回False
        """
        print(f"正在连接 WIFI: {ssid}...")
        
        # 连接 WIFI
        cmd = f"nmcli device wifi connect '{ssid}' password '{密码}' ifname wlan0"
        success, output, error = self.ssh.执行命令(cmd, use_sudo=True)
        
        if not success:
            print(f"✗ 连接 WIFI 失败: {error}")
            return False
        
        print("✓ 成功连接 WIFI")
        
        # 关闭网络清除服务
        print("正在配置网络服务...")
        self.ssh.执行命令("systemctl stop networkmanager-cleanup.service", use_sudo=True)
        self.ssh.执行命令("systemctl disable networkmanager-cleanup.service", use_sudo=True)
        
        # 开启自动连接
        cmd = f"nmcli connection modify '{ssid}' connection.autoconnect yes"
        self.ssh.执行命令(cmd, use_sudo=True)
        
        print("✓ WIFI 配置完成")
        time.sleep(2)
        
        return True
    
    def 获取机器狗IP(self) -> str:
        """
        获取机器狗的 IP 地址
        """
        while True:
            print("\n请选择连接方式:")
            print("1. AP网络: 192.168.234.1")
            print("2. 有线网络: 192.168.168.168")
            print("3. WIFI局域网 (需输入IP)")
            
            conn_type = input("请输入选项 (1/2/3): ").strip()
            
            if conn_type == "1":
                return "192.168.234.1"
            elif conn_type == "2":
                return "192.168.168.168"
            elif conn_type == "3":
                while True:
                    host_in = input("请输入机器狗 IP: ").strip()
                    if 是否禁止IP(host_in):
                        print("✗ 此 IP 不允许作为输入")
                        continue
                    return host_in
            else:
                print("✗ 无效的选项")
