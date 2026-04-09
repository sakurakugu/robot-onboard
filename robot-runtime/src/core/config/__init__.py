from pathlib import Path
from typing import Any

from sparkrobot_common import CONFIG_FILE, WORKSPACE_DIR, TomlParser, get_logger, 获取默认配置

logger = get_logger("robot-runtime")


class 运行时配置:
    """本体运行时只读配置。"""

    def __init__(self, config_file: Path | None = None) -> None:
        self.config_file = config_file or CONFIG_FILE
        self.workspace = WORKSPACE_DIR
        self._config: dict[str, dict[str, Any]] = {}
        self.加载()

    def 加载(self) -> None:
        """加载配置文件。"""
        default_config = 获取默认配置()

        if not self.config_file.exists():
            logger.warning("配置文件不存在，运行时将使用默认配置: %s", self.config_file)
            self._config = default_config
            return

        file_config = TomlParser.parse(self.config_file.read_text(encoding="utf-8"))
        self._config = self._合并配置(default_config, file_config)

    def _合并配置(
        self,
        default: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """合并配置，缺失项回退到默认值。"""
        merged: dict[str, dict[str, Any]] = {}

        for section, section_defaults in default.items():
            merged[section] = {}
            current_section = current.get(section, {})

            for key, default_value in section_defaults.items():
                if key in current_section:
                    value = current_section[key]
                    if value is None or (isinstance(value, str) and value == "" and default_value != ""):
                        merged[section][key] = default_value
                    else:
                        merged[section][key] = value
                else:
                    merged[section][key] = default_value

        return merged

    def 获取(self, key: str | None = None) -> Any:
        """获取配置。"""
        if key is None:
            return dict(self._config)

        if "." in key:
            section, subkey = key.split(".", 1)
            return self._config.get(section, {}).get(subkey)

        return self._config.get(key)


__all__ = ["运行时配置"]
