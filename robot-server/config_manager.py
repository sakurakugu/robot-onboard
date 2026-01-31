"""
配置管理模块 - 负责配置文件的读取、写入、验证和同步

功能：
1. 读取和写入配置文件
2. 配置验证和类型转换
3. 提供给 robot-agent 通过 HTTP API 访问

配置文件格式（简化TOML，一层嵌套）：
- 使用 [section] 表示分组
- 只允许 key = value 或 key = [array] 两种形式
- 只有一层嵌套，不会出现 [section.subsection]
- 所有配置项必须有默认值，不允许空值

配置文件位置：~/sparkrobot/config/config.toml
"""
from pathlib import Path
from typing import Any

from sparkrobot_common import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG_FIELDS,
    READONLY_FIELDS,
    TomlParser,
    get_all_sections,
    get_default_config,
    get_field_info,
)


class ConfigManager:
    """配置管理器 - 负责读写配置文件"""

    def __init__(self, config_file: Path | None = None):
        """初始化配置管理器

        Args:
            config_file: 配置文件路径，默认为 ~/sparkrobot/config/config.toml
        """
        self.config_file = config_file or CONFIG_FILE
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._config: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """加载配置文件"""
        if not self.config_file.exists():
            # 文件不存在，创建默认配置
            self._config = get_default_config()
            self._save()
            return

        # 读取现有配置
        file_config = TomlParser.parse(self.config_file.read_text(encoding="utf-8"))

        # 合并默认配置（填补缺失项）
        default_config = get_default_config()
        merged = self._merge_config(default_config, file_config)

        self._config = merged

        # 如果有变更（填补了缺失项），保存配置
        if merged != file_config:
            self._save()

    def _merge_config(
        self,
        default: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """合并配置，使用当前值覆盖默认值，但保留默认值中缺失的项"""
        merged: dict[str, dict[str, Any]] = {}

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

    def _save(self) -> None:
        """保存配置到文件"""
        # 构建字段信息用于注释
        field_info: dict[str, dict[str, Any]] = {}
        for f in DEFAULT_CONFIG_FIELDS:
            full_key = f"{f.section}.{f.key}"
            field_info[full_key] = {
                "description": f.description,
                "readonly": f.readonly,
            }

        content = TomlParser.dumps(
            self._config,
            sections=get_all_sections(),
            field_info=field_info,
            header_lines=[
                "# 机器狗配置文件",
                "# 自动生成，请勿手动编辑无效配置项",
            ],
        )

        self.config_file.write_text(content, encoding="utf-8")

    def get(self, key: str | None = None) -> Any:
        """获取配置

        Args:
            key: 配置键名，格式为 "section.key" 或 "section"，如果为None则返回全部配置
        
        Returns:
            配置值或配置字典
        """
        if key is None:
            return dict(self._config)

        if "." in key:
            section, subkey = key.split(".", 1)
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
        if "." not in key:
            return False

        # 检查只读字段
        if key in READONLY_FIELDS:
            return False

        section, subkey = key.split(".", 1)

        # 验证键名是否有效
        field = get_field_info(section, subkey)
        if field is None:
            return False

        # 验证并转换类型
        validated_value = self._validate_value(value, field)
        if validated_value is None and field.default != "":
            return False

        if section not in self._config:
            self._config[section] = {}

        self._config[section][subkey] = validated_value if validated_value is not None else field.default
        self._save()
        return True

    def set_many(self, updates: dict[str, Any]) -> dict[str, bool]:
        """批量设置配置项

        Args:
            updates: 要更新的配置项字典，支持两种格式：
                     1. 扁平格式: {"section.key": value}
                     2. 嵌套格式: {"section": {"key": value}}

        Returns:
            每个键的设置结果
        """
        results: dict[str, bool] = {}
        changed = False

        # 将嵌套格式展平为 "section.key" 格式
        flat_updates: dict[str, Any] = {}
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
            if "." not in key:
                results[key] = False
                continue

            # 检查只读字段
            if key in READONLY_FIELDS:
                results[key] = False
                continue

            section, subkey = key.split(".", 1)
            field = get_field_info(section, subkey)

            if field is None:
                results[key] = False
                continue

            validated_value = self._validate_value(value, field)
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

    def _validate_value(self, value: Any, field: Any) -> Any:
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
                    return value.lower() in ("true", "1", "yes", "on")
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

    def reset(self, key: str | None = None) -> bool:
        """重置配置为默认值

        Args:
            key: 要重置的键名（section.key），如果为None则重置全部（保留只读字段的值）

        Returns:
            是否重置成功
        """
        default_config = get_default_config()

        if key is None:
            # 重置全部，但保留只读字段的值
            old_readonly_values: dict[str, Any] = {}
            for readonly_key in READONLY_FIELDS:
                section, subkey = readonly_key.split(".", 1)
                if section in self._config and subkey in self._config[section]:
                    old_readonly_values[readonly_key] = self._config[section][subkey]

            self._config = default_config

            # 恢复只读字段的旧值
            for readonly_key, old_value in old_readonly_values.items():
                section, subkey = readonly_key.split(".", 1)
                if section in self._config:
                    self._config[section][subkey] = old_value
        else:
            if "." not in key:
                return False

            # 只读字段不能重置
            if key in READONLY_FIELDS:
                return False

            section, subkey = key.split(".", 1)
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
_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager


__all__ = [
    "ConfigManager",
    "get_config_manager",
    "CONFIG_DIR",
]
