"""
常量和配置字段定义

配置格式说明（一层嵌套）：
- 使用 [section] 表示分组
- 只允许 key = value 或 key = [array] 两种形式
- 只有一层嵌套，不会出现 [section.subsection]
- 所有配置项必须有默认值，不允许空值
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _生成UUID() -> str:
    """生成 UUID7"""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        import uuid
        return str(uuid.uuid7()) # type: ignore[attr-defined]


# ==================== 基础常量 ====================

ORG_NAME = "sparkrobot"  # 组织名
WORKSPACE_DIR = Path.home() / ORG_NAME
CONFIG_DIR = WORKSPACE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# robot-server 配置
ROBOT_SERVER_HOST = "127.0.0.1"
ROBOT_SERVER_PORT = 8080
ROBOT_SERVER_URL = f"http://{ROBOT_SERVER_HOST}:{ROBOT_SERVER_PORT}"

# 默认服务器地址
DEFAULT_SERVER_ADDR = "192.168.1.101"


# ==================== 配置字段定义 ====================

@dataclass
class 配置字段:
    """配置字段定义"""
    section: str      # 所属分组
    key: str          # 字段名
    default: Any      # 默认值
    description: str  # 描述
    value_type: str   # "string", "int", "float", "bool", "list"
    readonly: bool = False  # 是否只读
    options: list[str] | None = None  # 可选项

# 配置分组标题映射
CONFIG_SECTION_TITLES: dict[str, str] = {
    "robot": "机器人信息",
    "server": "服务器配置",
    "sdk": "SDK配置",
    "audio": "音频配置",
    "actions": "动作配置",
    "logging": "日志配置",
    "auth": "认证配置",
}

# 默认配置字段定义（一层嵌套结构）
DEFAULT_CONFIG_FIELDS: list[配置字段] = [
    # 机器人基本信息 [robot]
    配置字段("robot", "uuid", "", "机器人唯一标识（自动生成）", "string", readonly=True),
    配置字段("robot", "name", "", "机器人名称", "string"),
    配置字段("robot", "model", "agibot-d1", "机器人型号", "string", readonly=True),
    配置字段("robot", "agent_version", "0.0.0", "机器人代理版本", "string", readonly=True),
    配置字段("robot", "server_version", "0.0.0", "robot-server 版本", "string", readonly=True),
    配置字段("robot", "motion_control_version", "0.0.0", "机器人运控版本", "string", readonly=True),


    # 服务器配置 [server]
    配置字段("server", "server_url", f"ws://{DEFAULT_SERVER_ADDR}:9000", "服务器URL", "string"),
    配置字段("server", "business_url", "/api/v1/robot/business", "业务连接URL", "string"),
    配置字段("server", "audio_upload_url", "/api/v1/robot/audio/upload", "音频上传URL", "string"),
    配置字段("server", "audio_download_url", "/api/v1/robot/audio/download", "音频下载URL", "string"),
    配置字段("server", "reconnect_interval", 5, "重连间隔（秒）", "int"),
    配置字段("server", "heartbeat_interval", 30, "心跳间隔（秒）", "int"),

    # SDK配置 [sdk]
    配置字段("sdk", "enable_sdk_on_startup", True, "启动时是否开启SDK模式", "bool"),
    配置字段("sdk", "robot_ip", "127.0.0.1", "机器人SDK IP地址", "string", readonly=True),
    配置字段("sdk", "local_port", 43988, "本地SDK端口", "int", readonly=True),

    # 音频配置 [audio]
    配置字段("audio", "sample_rate", 16000, "音频采样率", "int"),
    配置字段("audio", "channels", 1, "音频通道数", "int"),
    配置字段("audio", "frame_duration_ms", 20, "音频帧时长（毫秒）", "int"),
    配置字段("audio", "vad_threshold", 0.015, "VAD阈值", "float"),
    配置字段("audio", "vad_silence_ms", 800, "VAD静音时长（毫秒）", "int"),
    配置字段("audio", "max_segment_ms", 30000, "最大音频片段时长（毫秒）", "int"),  # 从10000增加到30000ms
    配置字段("audio", "enable_streaming", False, "是否启用流式传输", "bool"),  # 改为False，禁用流式传输以支持一次性收集
    配置字段("audio", "input_device", "", "音频输入设备（空表示默认）", "string"),

    # 动作配置 [actions]
    配置字段("actions", "startup_behavior", "stop", "启动后状态：stop|lie_down|stand_up", "string", options=["stop", "lie_down", "stand_up"]),
    配置字段("actions", "exit_behavior", "lie_down", "退出后行为：lie_down|stand_up|stop", "string", options=["lie_down", "stand_up", "stop"]),

    # 日志配置 [logging]
    配置字段("logging", "level", "INFO", "日志级别：DEBUG|INFO|WARNING|ERROR", "string", options=["DEBUG", "INFO", "WARNING", "ERROR"]),
    配置字段("logging", "max_file_size_mb", 10, "日志文件最大大小（MB）", "int"),

    # 认证配置 [auth]
    配置字段("auth", "username", "sparkrobot", "登录用户名", "string", readonly=True),
    配置字段("auth", "password", "sparkrobot", "登录密码", "string", readonly=True),
    配置字段("auth", "session_timeout", 3600, "会话超时时间（秒）", "int"),
]

# 只读字段集合
READONLY_FIELDS: set[str] = {f"{f.section}.{f.key}" for f in DEFAULT_CONFIG_FIELDS if f.readonly}


# ==================== 配置工具函数 ====================

def _生成机器人名称(uuid_val: str) -> str:
    """生成机器人名称"""
    return f"机器狗-{uuid_val[:4]}"


def 获取所有分组() -> list[str]:
    """获取所有配置分组（保持顺序）"""
    seen: list[str] = []
    for f in DEFAULT_CONFIG_FIELDS:
        if f.section not in seen:
            seen.append(f.section)
    return seen


def 获取默认配置() -> dict[str, dict[str, Any]]:
    """获取默认配置字典（嵌套格式）"""
    config: dict[str, dict[str, Any]] = {}

    # 先生成 UUID
    uuid_val = _生成UUID()

    for field in DEFAULT_CONFIG_FIELDS:
        if field.section not in config:
            config[field.section] = {}

        if field.section == "robot" and field.key == "uuid":
            config[field.section][field.key] = uuid_val
        elif field.section == "robot" and field.key == "name":
            config[field.section][field.key] = _生成机器人名称(uuid_val)
        else:
            config[field.section][field.key] = field.default

    return config


def 获取字段信息(section: str, key: str) -> 配置字段 | None:
    """获取字段信息"""
    for field in DEFAULT_CONFIG_FIELDS:
        if field.section == section and field.key == key:
            return field
    return None


def 通过完整键名获取字段信息(full_key: str) -> 配置字段 | None:
    """通过完整键名获取字段信息"""
    if "." not in full_key:
        return None
    section, key = full_key.split(".", 1)
    return 获取字段信息(section, key)


def 获取配置项字段信息() -> list[dict[str, Any]]:
    """获取配置字段信息（用于前端展示）"""
    return [
        {
            "section": f.section,
            "key": f.key,
            "full_key": f"{f.section}.{f.key}",
            "default": f.default,
            "description": f.description,
            "type": f.value_type,
            "readonly": f.readonly,
            "options": f.options,
        }
        for f in DEFAULT_CONFIG_FIELDS
    ]


def 获取配置分组信息() -> list[dict[str, Any]]:
    """获取配置分组信息（用于前端展示），包含分组名、标题和有序字段列表"""
    sections: dict[str, dict[str, Any]] = {}
    for f in DEFAULT_CONFIG_FIELDS:
        if f.section not in sections:
            sections[f.section] = {
                "section": f.section,
                "title": CONFIG_SECTION_TITLES.get(f.section, f.section),
                "keys": [],
            }
        sections[f.section]["keys"].append(f.key)
    return list(sections.values())


__all__ = [
    "ORG_NAME",
    "WORKSPACE_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEFAULT_SERVER_ADDR",
    "DEFAULT_CONFIG_FIELDS",
    "ROBOT_SERVER_HOST",
    "ROBOT_SERVER_PORT",
    "ROBOT_SERVER_URL",
    "READONLY_FIELDS",
    "配置字段",
    "获取所有分组",
    "获取默认配置",
    "获取字段信息",
    "通过完整键名获取字段信息",
    "获取配置项字段信息",
    "CONFIG_SECTION_TITLES",
    "获取配置分组信息",
]
