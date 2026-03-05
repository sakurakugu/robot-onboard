"""
SparkRobot Common - 通用库

提供配置管理、日志、工具函数等通用功能。
"""

from sparkrobot_common.const import (
    CONFIG_DIR,
    CONFIG_FILE,
    CONFIG_SECTION_TITLES,
    DEFAULT_CONFIG_FIELDS,
    DEFAULT_SERVER_ADDR,
    # 基础常量
    ORG_NAME,
    READONLY_FIELDS,
    ROBOT_SERVER_HOST,
    ROBOT_SERVER_PORT,
    ROBOT_SERVER_URL,
    WORKSPACE_DIR,
    获取字段信息,
    获取所有分组,
    获取配置分组信息,
    获取配置项字段信息,
    获取默认配置,
    通过完整键名获取字段信息,
    # 配置字段
    配置字段,
)
from sparkrobot_common.logger import (
    configure_logger,
    get_logger,
)
from sparkrobot_common.toml_parser import TomlParser
from sparkrobot_common.utils import (
    生成UUID,
    获取项目版本,
    获取IPC路径,
    获取本机IP,
    检测机器人运控版本,
    生成机器人名称,
)

__version__ = "0.1.0"

__all__ = [
    # 版本
    "__version__",
    # 常量
    "ORG_NAME",
    "WORKSPACE_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ROBOT_SERVER_HOST",
    "ROBOT_SERVER_PORT",
    "ROBOT_SERVER_URL",
    "DEFAULT_SERVER_ADDR",
    # 配置字段
    "配置字段",
    "DEFAULT_CONFIG_FIELDS",
    "READONLY_FIELDS",
    "获取默认配置",
    "获取所有分组",
    "获取字段信息",
    "通过完整键名获取字段信息",
    "获取配置项字段信息",
    "CONFIG_SECTION_TITLES",
    "获取配置分组信息",
    # TOML 解析
    "TomlParser",
    # 日志
    "configure_logger",
    "get_logger",
    # 工具
    "生成UUID",
    "生成机器人名称",
    "获取本机IP",
    "获取IPC路径",
    "检测机器人运控版本",
    "获取项目版本",
]
