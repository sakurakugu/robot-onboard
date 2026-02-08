"""SDK 配置模块 - 处理机器狗 SDK 配置和运控管理"""

import re
import io
from typing import Optional
from ruamel.yaml import YAML


class SDK配置管理器:
    """SDK 配置管理器 - 处理 SDK 配置文件修改和运控重启"""

    def __init__(self, ssh管理器):
        self.ssh = ssh管理器
        self.auto_confirm = False  # 是否自动确认重启

    def 修改SDK配置(self, target_ip: str, target_port: int) -> bool:
        """修改 SDK 配置文件

        Args:
            target_ip: 目标 IP 地址
            target_port: 目标端口号

        Returns:
            成功返回True，失败返回False
        """
        print("正在修改 SDK 配置文件...")
        config_path = "/opt/export/config/sdk_config.yaml"

        # 读取配置文件
        success, content, error = self.ssh.执行命令(f"cat {config_path}", use_sudo=True)
        if not success:
            print(f"✗ 读取配置文件失败: {error}")
            return False

        # 使用 ruamel.yaml 解析与更新配置
        try:
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

        if not self.ssh.写入配置文件(modified_content, config_path, "SDK配置文件"):
            return False

        print(f"✓ SDK 配置文件已更新 (target_ip: {target_ip}, target_port: {target_port})")
        return True

    def 查看SDK配置(self) -> Optional[tuple[str, int]]:
        print("正在读取 SDK 配置文件...")
        config_path = "/opt/export/config/sdk_config.yaml"
        success, content, error = self.ssh.执行命令(f"cat {config_path}", use_sudo=True)
        if not success:
            print(f"✗ 读取配置文件失败: {error}")
            return None

        try:
            yaml = YAML()
            data_stream = io.StringIO(content)
            data = yaml.load(data_stream) or {}
            target_ip = str(data.get("target_ip", "")).strip()
            target_port_raw = data.get("target_port", "")
            target_port = int(target_port_raw) if str(target_port_raw).isdigit() else None
        except Exception as e:
            print(f"✗ YAML 解析失败: {e}")
            return None

        if target_port is None:
            print(f"当前 SDK 配置: target_ip={target_ip}, target_port=")
            return None

        print(f"当前 SDK 配置: target_ip={target_ip}, target_port={target_port}")
        return target_ip, target_port

    def 重置SDK配置(self) -> bool:
        return self.修改SDK配置("127.0.0.1", 43988)

    def 修改运控启动脚本(self, sdk_client_ip: Optional[str] = None) -> bool:
        """修改运控启动脚本

        Args:
            sdk_client_ip: SDK 客户端 IP (可选，用于 WIFI 模式)

        Returns:
            成功返回True，失败返回False
        """
        print("正在修改运控启动脚本...")
        script_path = "/opt/app_launch/start_motion_control.sh"

        # 读取脚本
        success, content, error = self.ssh.执行命令(f"cat {script_path}", use_sudo=True)
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

        if not self.ssh.写入配置文件(content, script_path, "运控启动脚本"):
            return False

        print("✓ 运控启动脚本已更新")
        return True

    def 查看运控配置(self) -> str:
        print("正在读取运控启动脚本...")
        script_path = "/opt/app_launch/start_motion_control.sh"
        success, content, error = self.ssh.执行命令(f"cat {script_path}", use_sudo=True)
        if not success:
            print(f"✗ 读取脚本失败: {error}")
            return ""

        match = re.search(r"export SDK_CLIENT_IP=['\"]?([^'\n\"]+)['\"]?", content)
        sdk_client_ip = match.group(1) if match else ""
        if sdk_client_ip:
            print(f"当前 SDK_CLIENT_IP: {sdk_client_ip}")
        else:
            print("当前 SDK_CLIENT_IP: 未设置")
        return sdk_client_ip

    def 重置运控配置(self) -> bool:
        return self.修改运控启动脚本(None)

    def 重启运动控制(self) -> bool:
        """重启运控服务

        Returns:
            成功返回True，失败返回False
        """
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
        success, output, error = self.ssh.执行命令("robot-launch restart 4", use_sudo=True)

        if success:
            print("✓ 运控重启成功")
            return True
        else:
            print(f"✗ 运控重启失败: {error}")
            return False
