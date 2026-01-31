#!/usr/bin/env python3
"""
配置管理模块 - 负责配置文件的读取、写入、验证和同步

配置文件格式（简化TOML，一层嵌套）：
- 使用 [section] 表示分组
- 只允许 key = value 或 key = [array] 两种形式
- 只有一层嵌套，不会出现 [section.subsection]
- 所有配置项必须有默认值，不允许空值

配置文件位置：~/sparkrobot/config/config.toml
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

# 配置目录
ORG_NAME = "sparkrobot"
WORKSPACE_DIR = Path.home() / ORG_NAME
CONFIG_DIR = WORKSPACE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# 确保目录存在
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class 配置字段:
    """配置字段定义"""
    section: str      # 所属分组
    key: str          # 字段名
    default: Any      # 默认值
    description: str  # 描述
    value_type: str   # "string", "int", "float", "bool", "list"
    readonly: bool = False  # 是否只读


def _生成UUID() -> str:
    """生成UUID"""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        import uuid
        return str(uuid.uuid7())


def _生成机器人名称(uuid_val: str) -> str:
    """生成机器人名称"""
    return f"机器狗-{uuid_val[:4]}"


# 默认配置定义（一层嵌套结构）
DEFAULT_CONFIG_FIELDS: List[配置字段] = [
    # 机器人基本信息 [robot]
    配置字段("robot", "uuid", "", "机器人唯一标识（自动生成）", "string", readonly=True),
    配置字段("robot", "name", "", "机器人名称", "string"),
    配置字段("robot", "model", "agibot-d1", "机器人型号", "string", readonly=True),
    配置字段("robot", "version", "0.0.0", "机器人运控版本", "string", readonly=True),
    
    # 服务器配置 [server]
    配置字段("server", "control_url", "ws://192.168.0.108:9000/api/v1/interaction/connect", "控制连接URL", "string"),
    配置字段("server", "business_url", "ws://192.168.0.108:9001/api/v1/interaction/connect", "业务连接URL", "string"),
    配置字段("server", "audio_upload_url", "ws://192.168.0.108:9002/api/v1/interaction/connect", "音频上传URL", "string"),
    配置字段("server", "audio_download_url", "ws://192.168.0.108:9003/api/v1/interaction/connect", "音频下载URL", "string"),
    配置字段("server", "reconnect_interval", 5, "重连间隔（秒）", "int"),
    配置字段("server", "heartbeat_interval", 30, "心跳间隔（秒）", "int"),
    
    # SDK配置 [sdk]
    配置字段("sdk", "robot_ip", "127.0.0.1", "机器人SDK IP地址", "string", readonly=True),
    配置字段("sdk", "local_port", 43988, "本地SDK端口", "int", readonly=True),
    
    # 音频配置 [audio]
    配置字段("audio", "sample_rate", 16000, "音频采样率", "int"),
    配置字段("audio", "channels", 1, "音频通道数", "int"),
    配置字段("audio", "frame_duration_ms", 20, "音频帧时长（毫秒）", "int"),
    配置字段("audio", "vad_threshold", 0.015, "VAD阈值", "float"),
    配置字段("audio", "vad_silence_ms", 800, "VAD静音时长（毫秒）", "int"),
    配置字段("audio", "max_segment_ms", 10000, "最大音频片段时长（毫秒）", "int"),
    配置字段("audio", "enable_streaming", True, "是否启用流式传输", "bool"),
    配置字段("audio", "input_device", "", "音频输入设备（空表示默认）", "string"),
    
    # 动作配置 [actions]
    配置字段("actions", "exit_behavior", "lie_down", "退出后行为：lie_down|stand_up|stop", "string"),
    
    # 日志配置 [logging]
    配置字段("logging", "level", "INFO", "日志级别：DEBUG|INFO|WARNING|ERROR", "string"),
    配置字段("logging", "max_file_size_mb", 10, "日志文件最大大小（MB）", "int"),
]

# 只读字段集合
READONLY_FIELDS: Set[str] = {f"{f.section}.{f.key}" for f in DEFAULT_CONFIG_FIELDS if f.readonly}


def 获取默认配置() -> Dict[str, Dict[str, Any]]:
    """获取默认配置字典（嵌套格式）"""
    config: Dict[str, Dict[str, Any]] = {}
    
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


def 获取配置字段信息() -> List[Dict[str, Any]]:
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
        }
        for f in DEFAULT_CONFIG_FIELDS
    ]


def 获取所有配置() -> List[str]:
    """获取所有配置分组"""
    seen = []
    for f in DEFAULT_CONFIG_FIELDS:
        if f.section not in seen:
            seen.append(f.section)
    return seen


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[Path] = None):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认为 ~/sparkrobot/config/config.toml
        """
        self.config_file = config_file or CONFIG_FILE
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self) -> None:
        """加载配置文件"""
        if not self.config_file.exists():
            # 文件不存在，创建默认配置
            self._config = 获取默认配置()
            self._save()
            return
        
        # 读取现有配置
        file_config = self._parse_toml(self.config_file.read_text(encoding="utf-8"))
        
        # 合并默认配置（填补缺失项）
        default_config = 获取默认配置()
        merged = self._合并配置(default_config, file_config)
        
        self._config = merged
        
        # 如果有变更（填补了缺失项），保存配置
        if merged != file_config:
            self._save()
    
    def _合并配置(self, default: Dict[str, Dict[str, Any]], current: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """合并配置，使用当前值覆盖默认值，但保留默认值中缺失的项"""
        merged: Dict[str, Dict[str, Any]] = {}
        
        for section, section_defaults in default.items():
            merged[section] = {}
            current_section = current.get(section, {})
            
            for key, default_value in section_defaults.items():
                if key in current_section:
                    value = current_section[key]
                    # 检查空值，如果是空值则使用默认值（除非默认值本身是空字符串）
                    if value is None or (isinstance(value, str) and value == "" and default_value != ""):
                        merged[section][key] = default_value
                    else:
                        merged[section][key] = value
                else:
                    merged[section][key] = default_value
        
        return merged
    
    def _parse_toml(self, content: str) -> Dict[str, Dict[str, Any]]:
        """解析简化的TOML格式（一层嵌套）"""
        config: Dict[str, Dict[str, Any]] = {}
        current_section = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 解析 [section]
            section_match = re.match(r'^\[([a-zA-Z_][a-zA-Z0-9_]*)\]$', line)
            if section_match:
                current_section = section_match.group(1)
                if current_section not in config:
                    config[current_section] = {}
                continue
            
            # 解析 key = value
            kv_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', line)
            if kv_match and current_section is not None:
                key = kv_match.group(1)
                value_str = kv_match.group(2).strip()
                config[current_section][key] = self._parse_value(value_str)
        
        return config
    
    def _parse_value(self, value_str: str) -> Any:
        """解析值字符串"""
        value_str = value_str.strip()
        
        # 布尔值
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
        
        # 数组
        if value_str.startswith('[') and value_str.endswith(']'):
            inner = value_str[1:-1].strip()
            if not inner:
                return []
            items = []
            for item in self._分割数组元素(inner):
                items.append(self._parse_value(item.strip()))
            return items
        
        # 字符串（带引号）
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        
        # 数字
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass
        
        return value_str
    
    def _分割数组元素(self, inner: str) -> List[str]:
        """分割数组元素"""
        items = []
        current = ""
        in_string = False
        string_char = None
        bracket_depth = 0
        
        for char in inner:
            if not in_string:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                    current += char
                elif char == '[':
                    bracket_depth += 1
                    current += char
                elif char == ']':
                    bracket_depth -= 1
                    current += char
                elif char == ',' and bracket_depth == 0:
                    items.append(current.strip())
                    current = ""
                else:
                    current += char
            else:
                current += char
                if char == string_char:
                    in_string = False
                    string_char = None
        
        if current.strip():
            items.append(current.strip())
        
        return items
    
    def _format_value(self, value: Any) -> str:
        """格式化值为TOML字符串"""
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, str):
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            formatted_items = [self._format_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        return f'"{value}"'
    
    def _save(self) -> None:
        """保存配置到文件"""
        lines = ["# 机器狗配置文件", "# 自动生成，请勿手动编辑无效配置项", ""]
        
        # 按分组写入配置
        sections = 获取所有配置()
        field_map: Dict[str, List[配置字段]] = {}
        for f in DEFAULT_CONFIG_FIELDS:
            if f.section not in field_map:
                field_map[f.section] = []
            field_map[f.section].append(f)
        
        for section in sections:
            if section not in self._config:
                continue
            
            lines.append(f"[{section}]")
            
            for field in field_map.get(section, []):
                if field.key in self._config[section]:
                    value = self._config[section][field.key]
                    formatted = self._format_value(value)
                    readonly_mark = " # (只读)" if field.readonly else ""
                    lines.append(f"# {field.description}{readonly_mark}")
                    lines.append(f"{field.key} = {formatted}")
            
            lines.append("")
        
        self.config_file.write_text('\n'.join(lines), encoding="utf-8")
    
    def get(self, key: Optional[str] = None) -> Any:
        """获取配置
        
        Args:
            key: 配置键名，格式为 "section.key" 或 "section"，如果为None则返回全部配置
        
        Returns:
            配置值或配置字典
        """
        if key is None:
            return dict(self._config)
        
        if '.' in key:
            section, subkey = key.split('.', 1)
            return self._config.get(section, {}).get(subkey)
        else:
            return self._config.get(key)
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项
        
        Args:
            key: 配置键名，格式为 "section.key"
            value: 配置值
        
        Returns:
            是否设置成功
        """
        if '.' not in key:
            return False
        
        # 检查只读字段
        if key in READONLY_FIELDS:
            return False
        
        section, subkey = key.split('.', 1)
        
        # 验证键名是否有效
        field = self._获取字段定义(section, subkey)
        if field is None:
            return False
        
        # 验证并转换类型
        validated_value = self._验证并转换值类型(value, field)
        if validated_value is None and field.default != "":
            return False
        
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section][subkey] = validated_value if validated_value is not None else field.default
        self._save()
        return True
    
    def set_many(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """批量设置配置项
        
        Args:
            updates: 要更新的配置项字典，支持两种格式：
                     1. 扁平格式: {"section.key": value}
                     2. 嵌套格式: {"section": {"key": value}}
        
        Returns:
            每个键的设置结果
        """
        results = {}
        changed = False
        
        # 将嵌套格式展平为 "section.key" 格式
        flat_updates = {}
        for key, value in updates.items():
            if isinstance(value, dict):
                # 嵌套格式: key 是 section, value 是 {subkey: subvalue}
                for subkey, subvalue in value.items():
                    flat_key = f"{key}.{subkey}"
                    flat_updates[flat_key] = subvalue
            else:
                # 扁平格式: key 是 "section.key"
                flat_updates[key] = value
        
        for key, value in flat_updates.items():
            if '.' not in key:
                results[key] = False
                continue
            
            # 检查只读字段
            if key in READONLY_FIELDS:
                results[key] = False
                continue
            
            section, subkey = key.split('.', 1)
            field = self._获取字段定义(section, subkey)
            
            if field is None:
                results[key] = False
                continue
            
            validated_value = self._验证并转换值类型(value, field)
            if validated_value is None and field.default != "":
                results[key] = False
            else:
                if section not in self._config:
                    self._config[section] = {}
                self._config[section][subkey] = validated_value if validated_value is not None else field.default
                results[key] = True
                changed = True
        
        if changed:
            self._save()
        
        return results
    
    def _获取字段定义(self, section: str, key: str) -> Optional[配置字段]:
        """获取字段定义"""
        for f in DEFAULT_CONFIG_FIELDS:
            if f.section == section and f.key == key:
                return f
        return None
    
    def _验证并转换值类型(self, value: Any, field: 配置字段) -> Any:
        """验证并转换值类型"""
        try:
            if field.value_type == "string":
                if value is None or value == "":
                    return field.default if field.default != "" else ""
                return str(value)
            elif field.value_type == "int":
                if value is None or value == "":
                    return field.default
                return int(value)
            elif field.value_type == "float":
                if value is None or value == "":
                    return field.default
                return float(value)
            elif field.value_type == "bool":
                if value is None or value == "":
                    return field.default
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif field.value_type == "list":
                if value is None:
                    return field.default if field.default else []
                if isinstance(value, list):
                    return value
                return [value]
        except (ValueError, TypeError):
            return None
        
        return value
    
    def reload(self) -> None:
        """重新加载配置"""
        self._load()
    
    def reset(self, key: Optional[str] = None) -> bool:
        """重置配置为默认值
        
        Args:
            key: 要重置的键名（section.key），如果为None则重置全部（保留只读字段的值）
        
        Returns:
            是否重置成功
        """
        default_config = 获取默认配置()
        
        if key is None:
            # 重置全部，但保留只读字段的值
            old_readonly_values = {}
            for readonly_key in READONLY_FIELDS:
                section, subkey = readonly_key.split('.', 1)
                if section in self._config and subkey in self._config[section]:
                    old_readonly_values[readonly_key] = self._config[section][subkey]
            
            self._config = default_config
            
            # 恢复只读字段的旧值
            for readonly_key, old_value in old_readonly_values.items():
                section, subkey = readonly_key.split('.', 1)
                if section in self._config:
                    self._config[section][subkey] = old_value
        else:
            if '.' not in key:
                return False
            
            # 只读字段不能重置
            if key in READONLY_FIELDS:
                return False
            
            section, subkey = key.split('.', 1)
            if section not in default_config or subkey not in default_config[section]:
                return False
            
            if section not in self._config:
                self._config[section] = {}
            self._config[section][subkey] = default_config[section][subkey]
        
        self._save()
        return True
    
    @property
    def config_path(self) -> Path:
        """获取配置文件路径"""
        return self.config_file
    
    @property
    def config_dir(self) -> Path:
        """获取配置目录路径"""
        return self.config_file.parent


# 全局配置管理器实例
_manager: Optional[ConfigManager] = None


def 获取全局配置管理器实例() -> ConfigManager:
    """get_config_manager"""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager
