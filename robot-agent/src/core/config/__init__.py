"""
配置管理模块（只读）

robot-agent 只能读取配置，写入配置需要通过 robot-server HTTP API。

功能：
1. 从本地文件读取配置
2. 通过 HTTP API 从 robot-server 获取配置
3. 通过 HTTP API 向 robot-server 写入配置
4. watchdog 文件监听实现热更新
5. 配置变更回调通知
"""
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from sparkrobot_common import (
    READONLY_FIELDS,  # 只读字段
    ROBOT_SERVER_URL,  # 机器人服务器 URL
    WORKSPACE_DIR,  # 工作目录
    TomlParser,
    获取默认配置,
)

# 尝试导入 watchdog
try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None  # type: ignore
    FileSystemEventHandler = object  # type: ignore

# 延迟导入 auth_client 以避免循环导入
def get_auth_client():
    """延迟导入认证客户端"""
    from ..auth_client import get_auth_client as _get_auth_client
    return _get_auth_client()

class ConfigFileHandler(FileSystemEventHandler if HAS_WATCHDOG else object):  # type: ignore
    """配置文件变更事件处理器"""

    def __init__(self, config_manager: "Config", config_file: Path):
        self.config_manager = config_manager
        self.config_file = config_file
        self._最后修改时间 = 0.0
        self._防抖秒数 = 0.5  # 防抖时间

    # 不能修改成中文，该函数自动触发
    def on_modified(self, event: Any) -> None:
        """处理文件修改事件"""
        if not HAS_WATCHDOG:
            return
        if not isinstance(event, FileModifiedEvent):
            return

        # 检查是否是我们关注的文件
        if Path(str(event.src_path)).resolve() != self.config_file.resolve():
            return

        # 防抖：避免短时间内多次触发
        当前时间 = time.time()
        if 当前时间 - self._最后修改时间 < self._防抖秒数:
            return
        self._最后修改时间 = 当前时间

        # 触发配置重载
        self.config_manager._处理配置文件变更()


class Config:
    """配置管理器（只读）

    特性：
    - 单例模式
    - 只读本地配置文件
    - 通过 HTTP API 写入配置到 robot-server
    - 支持 watchdog 文件监听实现热更新
    - 配置变更回调通知
    - 一层嵌套格式：{section: {key: value}}
    """

    _instance: "Config | None" = None
    _lock = threading.Lock()

    def __init__(self, workspace: Path | None = None):
        """初始化配置管理器

        Args:
            workspace: 工作目录，默认为 ~/sparkrobot
        """
        if workspace is None:
            workspace = WORKSPACE_DIR

        self.base_dir = workspace
        self.config_dir = workspace / "config"
        self.config_file = self.config_dir / "config.toml"

        # 确保目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 配置数据（嵌套格式：{section: {key: value}}）
        self._config: dict[str, dict[str, Any]] = {}

        # 配置变更回调
        self._on_change_callbacks: list[Callable[[dict[str, dict[str, Any]]], None]] = []

        # watchdog 观察器
        self._observer: Any = None
        self._watching = False

        # 加载配置
        self._load()

        # 配置认证客户端
        self._configure_auth_client()

    @classmethod
    def instance(cls, workspace: Path | None = None) -> "Config":
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(workspace)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（用于测试）"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.停止监听()
                cls._instance = None

    def _load(self) -> None:
        """加载配置（只读）"""
        # 从本地文件加载
        if self.config_file.exists():
            file_config = TomlParser.parse(self.config_file.read_text(encoding="utf-8"))
        else:
            file_config = {}

        # 合并默认配置
        default_config = 获取默认配置()
        self._config = self._merge_config(default_config, file_config)

    def _merge_config(
        self,
        default: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """合并配置，保留当前值但填补缺失项"""
        merged: dict[str, dict[str, Any]] = {}

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

    # ==================== 配置访问接口 ====================

    def get(self, key: str | None = None) -> Any:
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

    def _configure_auth_client(self) -> None:
        """配置认证客户端"""
        try:
            auth_config = self._config.get("auth", {})
            username = auth_config.get("username", "sparkrobot")
            password = auth_config.get("password", "sparkrobot")
            session_timeout = auth_config.get("session_timeout", 3600)

            auth_client = get_auth_client()
            auth_client.configure(username, password, session_timeout)
        except Exception as e:
            print(f"[Config] 配置认证客户端失败: {e}")

    def 设置(
        self,
        key: str,
        value: Any,
        server_url: str | None = None,
    ) -> bool:
        """通过 robot-server 设置配置项

        Args:
            key: 配置键名，格式为 "section.key"
            value: 配置值
            server_url: 服务器地址，默认使用 ROBOT_SERVER_URL

        Returns:
            是否设置成功
        """
        url = server_url or ROBOT_SERVER_URL
        api_url = f"{url}/api/v1/config"

        try:
            data = json.dumps({key: value}).encode("utf-8")
            req = urllib.request.Request(api_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")

            # 添加认证信息
            auth_client = get_auth_client()
            if not auth_client.add_auth_to_request(req):
                print("[Config] 警告: 无法添加认证信息")

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("success"):
                    # 重新加载本地配置
                    self.reload()
                    return True
                return False

        except Exception as e:
            print(f"[Config] 设置配置失败: {e}")
            return False

    def 批量设置(
        self,
        updates: dict[str, Any],
        server_url: str | None = None,
    ) -> dict[str, bool]:
        """通过 robot-server 批量设置配置项

        Args:
            updates: 要更新的配置项字典
            server_url: 服务器地址

        Returns:
            每个键的设置结果
        """
        url = server_url or ROBOT_SERVER_URL
        api_url = f"{url}/api/v1/config"

        try:
            data = json.dumps(updates).encode("utf-8")
            req = urllib.request.Request(api_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")

            # 添加认证信息
            auth_client = get_auth_client()
            if not auth_client.add_auth_to_request(req):
                print("[Config] 警告: 无法添加认证信息")

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("success"):
                    self.reload()
                return result.get("results", {})

        except Exception as e:
            print(f"[Config] 批量设置配置失败: {e}")
            return dict.fromkeys(updates.keys(), False)

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

    def 启动监听(self) -> bool:
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

    def 停止监听(self) -> None:
        """停止配置文件监听"""
        if self._observer is not None and self._watching:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._watching = False
            print("[Config] 已停止配置文件监听")

    def _处理配置文件变更(self) -> None:
        """配置文件变更处理"""
        print("[Config] 检测到配置文件变更，重新加载...")
        try:
            old_config = dict(self._config)
            self._load()

            if old_config != self._config:
                self._通知配置变更()
                print("[Config] 配置已更新")
        except Exception as e:
            print(f"[Config] 重新加载配置失败: {e}")

    # ==================== 配置变更回调 ====================

    def 注册配置变更回调(self, callback: Callable[[dict[str, dict[str, Any]]], None]) -> None:
        """注册配置变更回调

        Args:
            callback: 回调函数，参数为新的配置字典
        """
        if callback not in self._on_change_callbacks:
            self._on_change_callbacks.append(callback)

    def 移除配置变更回调(self, callback: Callable[[dict[str, dict[str, Any]]], None]) -> None:
        """移除配置变更回调"""
        if callback in self._on_change_callbacks:
            self._on_change_callbacks.remove(callback)

    def _通知配置变更(self) -> None:
        """通知配置变更"""
        for callback in self._on_change_callbacks:
            try:
                callback(dict(self._config))
            except Exception as e:
                print(f"[Config] 配置变更回调执行失败: {e}")

    # ==================== HTTP 同步 ====================

    # sync_from_server
    def 获取配置(self, server_url: str | None = None) -> bool:
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

            # 添加认证信息（注意：GET /api/v1/config 可能不需要认证，但添加也无妨）
            auth_client = get_auth_client()
            auth_client.add_auth_to_request(req)

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

                    self._通知配置变更()
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
        self._通知配置变更()


# 便捷访问函数
def get_config() -> Config:
    """获取配置管理器实例"""
    return Config.instance()


__all__ = [
    "Config",
    "get_config",
    "HAS_WATCHDOG",
]
