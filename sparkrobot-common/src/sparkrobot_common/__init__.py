"""
SparkRobot Common - 通用库

提供配置管理、日志、工具函数等通用功能。
"""

from sparkrobot_common.const import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG_FIELDS,
    DEFAULT_SERVER_ADDR,
    # 基础常量
    ORG_NAME,
    READONLY_FIELDS,
    ROBOT_SERVER_HOST,
    ROBOT_SERVER_PORT,
    ROBOT_SERVER_URL,
    WORKSPACE_DIR,
    # 配置字段
    ConfigField,
    get_all_sections,
    get_config_field_info,
    get_default_config,
    get_field_by_full_key,
    get_field_info,
)
from sparkrobot_common.logger import (
    configure_logger,
    get_logger,
)
from sparkrobot_common.toml_parser import TomlParser
from sparkrobot_common.utils import (
    detect_robot_version,
    generate_robot_name,
    generate_uuid,
    get_ipc_path,
    get_local_ip,
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
    "ConfigField",
    "DEFAULT_CONFIG_FIELDS",
    "READONLY_FIELDS",
    "get_default_config",
    "get_all_sections",
    "get_field_info",
    "get_field_by_full_key",
    "get_config_field_info",
    # TOML 解析
    "TomlParser",
    # 日志
    "configure_logger",
    "get_logger",
    # 工具
    "generate_uuid",
    "generate_robot_name",
    "get_local_ip",
    "get_ipc_path",
    "detect_robot_version",
]
