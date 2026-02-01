"""
简化 TOML 解析器

支持一层嵌套的 TOML 格式：
- [section] 表示分组
- key = value 或 key = [array]
- 不支持 [section.subsection] 多层嵌套
"""
import re
from typing import Any


class TomlParser:
    """简化的 TOML 解析器（一层嵌套）"""

    @staticmethod
    def parse(content: str) -> dict[str, dict[str, Any]]:
        """解析 TOML 字符串

        Args:
            content: TOML 格式的字符串

        Returns:
            嵌套字典 {section: {key: value}}
        """
        config: dict[str, dict[str, Any]] = {}
        current_section: str | None = None

        for line in content.split("\n"):
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue

            # 解析 [section]
            section_match = re.match(r"^\[([a-zA-Z_][a-zA-Z0-9_]*)\]$", line)
            if section_match:
                current_section = section_match.group(1)
                if current_section not in config:
                    config[current_section] = {}
                continue

            # 解析 key = value
            kv_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$", line)
            if kv_match and current_section is not None:
                key = kv_match.group(1)
                value_str = kv_match.group(2).strip()
                config[current_section][key] = TomlParser._解析值字符串(value_str)

        return config

    @staticmethod
    def _解析值字符串(value_str: str) -> Any:
        """解析值字符串"""
        value_str = value_str.strip()

        # 布尔值
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # 数组
        if value_str.startswith("[") and value_str.endswith("]"):
            inner = value_str[1:-1].strip()
            if not inner:
                return []
            items = []
            for item in TomlParser._分割数组元素(inner):
                items.append(TomlParser._解析值字符串(item.strip()))
            return items

        # 字符串（带引号）
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]

        # 数字
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        return value_str

    @staticmethod
    def _分割数组元素(inner: str) -> list[str]:
        """分割数组元素"""
        items: list[str] = []
        current = ""
        in_string = False
        string_char: str | None = None
        bracket_depth = 0

        for char in inner:
            if not in_string:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                    current += char
                elif char == "[":
                    bracket_depth += 1
                    current += char
                elif char == "]":
                    bracket_depth -= 1
                    current += char
                elif char == "," and bracket_depth == 0:
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

    @staticmethod
    def format_value(value: Any) -> str:
        """格式化值为 TOML 字符串"""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            formatted_items = [TomlParser.format_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        return f'"{value}"'

    @staticmethod
    def dumps(
        config: dict[str, dict[str, Any]],
        sections: list[str] | None = None,
        field_info: dict[str, dict[str, Any]] | None = None,
        header_lines: list[str] | None = None,
    ) -> str:
        """将配置字典转换为 TOML 字符串

        Args:
            config: 嵌套配置字典
            sections: 分组顺序列表，默认按字典顺序
            field_info: 字段信息 {section.key: {description, readonly}}，用于添加注释
            header_lines: 文件头部注释

        Returns:
            TOML 格式字符串
        """
        lines: list[str] = []

        if header_lines:
            lines.extend(header_lines)
            lines.append("")

        section_list = sections or list(config.keys())

        for section in section_list:
            if section not in config:
                continue

            lines.append(f"[{section}]")

            for key, value in config[section].items():
                formatted = TomlParser.format_value(value)

                # 添加注释
                if field_info:
                    full_key = f"{section}.{key}"
                    info = field_info.get(full_key, {})
                    desc = info.get("description", "")
                    readonly = info.get("readonly", False)

                    if desc:
                        readonly_mark = " (只读)" if readonly else ""
                        lines.append(f"# {desc}{readonly_mark}")

                lines.append(f"{key} = {formatted}")

            lines.append("")

        return "\n".join(lines)


__all__ = ["TomlParser"]
