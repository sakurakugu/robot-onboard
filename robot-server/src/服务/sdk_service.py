"""SDK 配置服务模块 - 处理机器狗本地 SDK 配置和运控管理

提供以下功能：
1. 修改、查看、重置 SDK 配置文件 (/opt/export/config/sdk_config.yaml)
2. 修改、查看、重置运控启动脚本 (/opt/app_launch/start_motion_control.sh)
3. 重启运控服务
"""

import io
import re
import subprocess
from pathlib import Path
from typing import TypedDict

from ruamel.yaml import YAML


class SDK配置(TypedDict):
    """SDK 配置信息"""
    target_ip: str
    target_port: int


class 运控配置(TypedDict):
    """运控配置信息"""
    sdk_client_ip: str


SDK_CONFIG_PATH = "/opt/export/config/sdk_config.yaml"
MOTION_CONTROL_SCRIPT_PATH = "/opt/app_launch/start_motion_control.sh"


def _执行命令(command: str, use_sudo: bool = False) -> tuple[bool, str, str]:
    """执行本地命令

    Args:
        command: 要执行的命令
        use_sudo: 是否使用 sudo 权限

    Returns:
        (成功标志, 标准输出, 错误输出)
    """
    if use_sudo:
        command = f"sudo {command}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        success = result.returncode == 0
        return success, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "命令执行超时"
    except Exception as e:
        return False, "", str(e)


def _读取文件(file_path: str) -> tuple[bool, str, str]:
    """读取文件内容

    Args:
        file_path: 文件路径

    Returns:
        (成功标志, 文件内容, 错误信息)
    """
    return _执行命令(f"cat {file_path}", use_sudo=True)


def _写入文件(content: str, file_path: str) -> tuple[bool, str]:
    """写入文件内容

    Args:
        content: 要写入的内容
        file_path: 文件路径

    Returns:
        (成功标志, 错误信息)
    """
    # 创建临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp") as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # 复制临时文件到目标位置
        success, _, error = _执行命令(f"cp {tmp_path} {file_path}", use_sudo=True)
        if not success:
            return False, f"写入文件失败: {error}"

        # 设置权限
        _执行命令(f"chmod 644 {file_path}", use_sudo=True)

        return True, ""
    finally:
        # 删除临时文件
        Path(tmp_path).unlink(missing_ok=True)


# ==================== SDK 配置相关 ====================

def 查看SDK配置() -> tuple[bool, SDK配置 | None, str]:
    """查看当前 SDK 配置

    Returns:
        (成功标志, SDK配置, 错误信息)
    """
    success, content, error = _读取文件(SDK_CONFIG_PATH)
    if not success:
        return False, None, f"读取配置文件失败: {error}"

    try:
        yaml = YAML()
        data_stream = io.StringIO(content)
        data = yaml.load(data_stream) or {}

        target_ip = str(data.get("target_ip", "")).strip()
        target_port_raw = data.get("target_port", "")
        target_port = int(target_port_raw) if str(target_port_raw).isdigit() else 0

        return True, SDK配置(target_ip=target_ip, target_port=target_port), ""
    except Exception as e:
        return False, None, f"YAML 解析失败: {e}"


def 修改SDK配置(target_ip: str, target_port: int) -> tuple[bool, str]:
    """修改 SDK 配置文件

    Args:
        target_ip: 目标 IP 地址
        target_port: 目标端口号

    Returns:
        (成功标志, 错误信息)
    """
    # 读取配置文件
    success, content, error = _读取文件(SDK_CONFIG_PATH)
    if not success:
        return False, f"读取配置文件失败: {error}"

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
        data["target_ip"] = str(target_ip)
        data["target_port"] = int(target_port)

        # 生成新的 YAML 内容
        out_stream = io.StringIO()
        yaml.dump(data, out_stream)
        modified_content = out_stream.getvalue()
    except Exception as e:
        return False, f"YAML 解析/生成失败: {e}"

    # 写入文件
    success, error = _写入文件(modified_content, SDK_CONFIG_PATH)
    if not success:
        return False, error

    return True, ""


def 重置SDK配置() -> tuple[bool, str]:
    """重置 SDK 配置为默认值 (127.0.0.1:43988)

    Returns:
        (成功标志, 错误信息)
    """
    return 修改SDK配置("127.0.0.1", 43988)


# ==================== 运控配置相关 ====================

def 查看运控配置() -> tuple[bool, 运控配置 | None, str]:
    """查看当前运控配置

    Returns:
        (成功标志, 运控配置, 错误信息)
    """
    success, content, error = _读取文件(MOTION_CONTROL_SCRIPT_PATH)
    if not success:
        return False, None, f"读取脚本失败: {error}"

    match = re.search(r"export SDK_CLIENT_IP=['\"]?([^'\n\"]+)['\"]?", content)
    sdk_client_ip = match.group(1) if match else ""

    return True, 运控配置(sdk_client_ip=sdk_client_ip), ""


def 修改运控配置(sdk_client_ip: str | None) -> tuple[bool, str]:
    """修改运控启动脚本

    Args:
        sdk_client_ip: SDK 客户端 IP (None 表示清除配置，用于 AP/有线直连模式)

    Returns:
        (成功标志, 错误信息)
    """
    # 读取脚本
    success, content, error = _读取文件(MOTION_CONTROL_SCRIPT_PATH)
    if not success:
        return False, f"读取脚本失败: {error}"

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

    # 写入文件
    success, error = _写入文件(content, MOTION_CONTROL_SCRIPT_PATH)
    if not success:
        return False, error

    return True, ""


def 重置运控配置() -> tuple[bool, str]:
    """重置运控配置（清除 SDK_CLIENT_IP）

    Returns:
        (成功标志, 错误信息)
    """
    return 修改运控配置(None)


# ==================== 运控服务管理 ====================

def 重启运控服务() -> tuple[bool, str]:
    """重启运控服务

    Returns:
        (成功标志, 错误信息)
    """
    success, output, error = _执行命令("robot-launch restart 4", use_sudo=True)

    if success:
        return True, ""
    else:
        return False, f"运控重启失败: {error}"
