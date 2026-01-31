"""
配置管理模块

功能：
1. 从 robot-server 通过 HTTP 获取配置
2. 使用 watchdog 监听配置文件变化实现热更新
3. 本地配置文件读写（一层嵌套 TOML 格式）
4. 配置变更回调通知

配置格式：
- 使用 [section] 表示分组
- 只允许 key = value 或 key = [array] 两种形式
- 只有一层嵌套，不会出现 [section.subsection]
- 所有配置项必须有默认值，不允许空值
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .const import (
    APP_NAME,
    DEFAULT_CONFIG_FIELDS,
    READONLY_FIELDS,
    ROBOT_SERVER_URL,
    WORKSPACE_DIR,
    获取默认配置,
    get_field_info,
    获取所有配置,
)

# 尝试导入 watchdog
try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None
    FileSystemEventHandler = object


class ConfigFileHandler(FileSystemEventHandler if HAS_WATCHDOG else object):
    """配置文件变更事件处理器"""

    def __init__(self, config_manager: "Config", config_file: Path):
        self.config_manager = config_manager
        self.config_file = config_file
        self._last_modified = 0
        self._debounce_seconds = 0.5  # 防抖时间

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent):
            return

        # 检查是否是我们关注的文件
        if Path(event.src_path).resolve() != self.config_file.resolve():
            return

        # 防抖：避免短时间内多次触发
        current_time = time.time()
        if current_time - self._last_modified < self._debounce_seconds:
            return
        self._last_modified = current_time

        # 触发配置重载
        self.config_manager._on_file_changed()


class Config:
    """配置管理器

    特性：
    - 单例模式
    - 支持从 robot-server HTTP API 获取配置
    - 支持 watchdog 文件监听实现热更新
    - 配置变更回调通知
    - 一层嵌套格式：{section: {key: value}}
    """

    _instance: Optional["Config"] = None
    _lock = threading.Lock()

    def __init__(self, workspace: Optional[Path] = None, project_name: str = APP_NAME):
        """初始化配置管理器

        Args:
            workspace: 工作目录，默认为 ~/sparkrobot
            project_name: 项目名称
        """
        if workspace is None:
            workspace = WORKSPACE_DIR

        self.base_dir = workspace
        self.config_dir = workspace / "config"
        self.project_name = project_name
        self.config_file = self.config_dir / "config.toml"

        # 确保目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 配置数据（嵌套格式：{section: {key: value}}）
        self._config: Dict[str, Dict[str, Any]] = {}

        # 配置变更回调
        self._on_change_callbacks: List[Callable[[Dict[str, Dict[str, Any]]], None]] = []

        # watchdog 观察器
        self._observer = None  # type: ignore
        self._watching = False

        # 加载配置
        self._load()

    @classmethod
    def instance(cls, workspace: Optional[Path] = None, project_name: Optional[str] = None) -> "Config":
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(workspace, project_name or APP_NAME)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（用于测试）"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop_watching()
                cls._instance = None

    def _load(self) -> None:
        """加载配置"""
        # 优先尝试从本地文件加载
        if self.config_file.exists():
            file_config = self._parse_toml(self.config_file.read_text(encoding="utf-8"))
        else:
            file_config = {}

        # 合并默认配置
        default_config = 获取默认配置()
        self._config = self._合并配置(default_config, file_config)

        # 保存配置（填补缺失项）
        if self._config != file_config:
            self._save()

    def _合并配置(self, default: Dict[str, Dict[str, Any]], current: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """合并配置，保留当前值但填补缺失项"""
        merged: Dict[str, Dict[str, Any]] = {}

        for section, section_defaults in default.items():
            merged[section] = {}
            current_section = current.get(section, {})

            for key, default_value in section_defaults.items():
                if key in current_section:
                    value = current_section[key]
                    # 检查空值
                    if value is None or (isinstance(value, str) and value == "" and default_value != ""):
                        merged[section][key] = default_value
                    else:
                        merged[section][key] = value
                else:
                    merged[section][key] = default_value

        return merged

    def _parse_toml(self, content: str) -> Dict[str, Dict[str, Any]]:
        """解析一层嵌套的 TOML 格式"""
        config: Dict[str, Dict[str, Any]] = {}
        current_section = None

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
                config[current_section][key] = self._parse_value(value_str)

        return config

    def _parse_value(self, value_str: str) -> Any:
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
            for item in self._分割数组元素(inner):
                items.append(self._parse_value(item.strip()))
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

    def _format_value(self, value: Any) -> str:
        """格式化值为TOML字符串"""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
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
        field_map: Dict[str, List] = {}
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

        self.config_file.write_text("\n".join(lines), encoding="utf-8")

    # ==================== 配置访问接口 ====================

    def get(self, key: Optional[str] = None) -> Any:
        """获取配置

        Args:
            key: 配置键名，支持格式：
                 - None: 返回全部配置（嵌套格式）
                 - "section": 返回整个分组
                 - "section.key": 返回具体配置项

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
        validated_value = self._验证并转换值类型(value, field)
        if validated_value is None and field.default != "":
            return False

        if section not in self._config:
            self._config[section] = {}

        old_value = self._config[section].get(subkey)
        self._config[section][subkey] = validated_value if validated_value is not None else field.default

        # 保存并通知
        self._save()
        if old_value != self._config[section][subkey]:
            self._notify_change()

        return True

    def _验证并转换值类型(self, value: Any, field) -> Any:
        """验证并转换值类型"""
        try:
            if field.value_type == "string":
                return str(value) if value is not None else ""
            elif field.value_type == "int":
                return int(value)
            elif field.value_type == "float":
                return float(value)
            elif field.value_type == "bool":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            elif field.value_type == "list":
                if isinstance(value, list):
                    return value
                return [value] if value else []
        except (ValueError, TypeError):
            return None
        return value

    # ==================== 便捷访问属性 ====================

    @property
    def robot_uuid(self) -> str:
        return self.get("robot.uuid") or ""

    @property
    def robot_name(self) -> str:
        return self.get("robot.name") or ""

    @property
    def robot_model(self) -> str:
        return self.get("robot.model") or "agibot-d1"

    @property
    def robot_version(self) -> str:
        return self.get("robot.version") or "0.0.0"

    @property
    def server_control_url(self) -> str:
        return self.get("server.control_url") or ""

    @property
    def server_business_url(self) -> str:
        return self.get("server.business_url") or ""

    @property
    def server_audio_upload_url(self) -> str:
        return self.get("server.audio_upload_url") or ""

    @property
    def server_audio_download_url(self) -> str:
        return self.get("server.audio_download_url") or ""

    @property
    def server_reconnect_interval(self) -> int:
        return self.get("server.reconnect_interval") or 5

    @property
    def server_heartbeat_interval(self) -> int:
        return self.get("server.heartbeat_interval") or 30

    @property
    def sdk_robot_ip(self) -> str:
        return self.get("sdk.robot_ip") or "127.0.0.1"

    @property
    def sdk_local_port(self) -> int:
        return self.get("sdk.local_port") or 43988

    @property
    def audio_sample_rate(self) -> int:
        return self.get("audio.sample_rate") or 16000

    @property
    def audio_channels(self) -> int:
        return self.get("audio.channels") or 1

    @property
    def audio_frame_duration_ms(self) -> int:
        return self.get("audio.frame_duration_ms") or 20

    @property
    def audio_vad_threshold(self) -> float:
        return self.get("audio.vad_threshold") or 0.015

    @property
    def audio_vad_silence_ms(self) -> int:
        return self.get("audio.vad_silence_ms") or 800

    @property
    def audio_max_segment_ms(self) -> int:
        return self.get("audio.max_segment_ms") or 10000

    @property
    def audio_enable_streaming(self) -> bool:
        return self.get("audio.enable_streaming") or True

    @property
    def audio_input_device(self) -> str:
        return self.get("audio.input_device") or ""

    @property
    def actions_exit_behavior(self) -> str:
        return self.get("actions.exit_behavior") or "lie_down"

    @property
    def logging_level(self) -> str:
        return self.get("logging.level") or "INFO"

    @property
    def logging_max_file_size_mb(self) -> int:
        return self.get("logging.max_file_size_mb") or 10

    # ==================== watchdog 文件监听 ====================

    def 启动配置文件监听(self) -> bool:
        """启动配置文件监听

        Returns:
            是否成功启动监听
        """
        if not HAS_WATCHDOG:
            print("[Config] watchdog 未安装，无法启动文件监听")
            return False

        if self._watching:
            return True

        try:
            self._observer = Observer()
            handler = ConfigFileHandler(self, self.config_file)
            self._observer.schedule(handler, str(self.config_dir), recursive=False)
            self._observer.start()
            self._watching = True
            print(f"[Config] 已启动配置文件监听: {self.config_file}")
            return True
        except Exception as e:
            print(f"[Config] 启动文件监听失败: {e}")
            return False

    def 停止配置文件监听(self) -> None:
        """停止配置文件监听"""
        if self._observer is not None and self._watching:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._watching = False
            print("[Config] 已停止配置文件监听")

    def _on_file_changed(self) -> None:
        """配置文件变更处理"""
        print("[Config] 检测到配置文件变更，重新加载...")
        try:
            old_config = dict(self._config)
            self._load()

            if old_config != self._config:
                self._notify_change()
                print("[Config] 配置已更新")
        except Exception as e:
            print(f"[Config] 重新加载配置失败: {e}")

    # ==================== 配置变更回调 ====================

    def 如果配置变化(self, callback: Callable[[Dict[str, Dict[str, Any]]], None]) -> None:
        """注册配置变更回调

        Args:
            callback: 回调函数，参数为新的配置字典
        """
        if callback not in self._on_change_callbacks:
            self._on_change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[Dict[str, Dict[str, Any]]], None]) -> None:
        """移除配置变更回调"""
        if callback in self._on_change_callbacks:
            self._on_change_callbacks.remove(callback)

    def _notify_change(self) -> None:
        """通知配置变更"""
        for callback in self._on_change_callbacks:
            try:
                callback(dict(self._config))
            except Exception as e:
                print(f"[Config] 配置变更回调执行失败: {e}")

    # ==================== HTTP 同步 ====================

    def sync_from_server(self, server_url: Optional[str] = None) -> bool:
        """从 robot-server 同步配置

        Args:
            server_url: 服务器地址，默认使用 ROBOT_SERVER_URL

        Returns:
            是否同步成功
        """
        url = server_url or ROBOT_SERVER_URL
        api_url = f"{url}/api/v1/config"

        try:
            req = urllib.request.Request(api_url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("success") and "config" in data:
                    server_config = data["config"]

                    # 合并配置（保留只读字段的当前值）
                    for section, section_data in server_config.items():
                        if section not in self._config:
                            self._config[section] = {}

                        for key, value in section_data.items():
                            full_key = f"{section}.{key}"
                            if full_key not in READONLY_FIELDS:
                                self._config[section][key] = value

                    self._save()
                    self._notify_change()
                    print(f"[Config] 已从服务器同步配置: {api_url}")
                    return True
                else:
                    print(f"[Config] 服务器返回错误: {data}")
                    return False

        except urllib.error.URLError as e:
            print(f"[Config] 无法连接服务器 {api_url}: {e}")
            return False
        except Exception as e:
            print(f"[Config] 同步配置失败: {e}")
            return False

    def reload(self) -> None:
        """重新加载配置"""
        self._load()
        self._notify_change()


# 便捷访问函数
def get_config() -> Config:
    """获取配置管理器实例"""
    return Config.instance()


__all__ = [
    "Config",
    "get_config",
    "HAS_WATCHDOG",
]
