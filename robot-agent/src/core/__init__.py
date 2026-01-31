"""
Core 模块

提供配置管理功能。日志和工具函数请从 sparkrobot_common 导入。
"""

from core.config import Config, get_config

__all__ = [
    "Config",
    "get_config",
]
