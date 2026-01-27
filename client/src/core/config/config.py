from pathlib import Path
from typing import Any, Dict, Optional

from core.config import SERVER_ADDR, WORKSPACE_DIR
from core.utils import generate_uuid

try:
    import tomli
    import tomli_w
except ImportError:
    raise RuntimeError("tomli 或 tomli_w 没有安装") from None


class Config:
    _instance: Optional["Config"] = None

    def __init__(self, workspace: Optional[Path] = None, project_name: str = "robot-chat"):
        if workspace is None:
            workspace = WORKSPACE_DIR
        self.base_dir = workspace
        self.config_dir = self.base_dir / "config"
        self.project_name = project_name
        self.global_config_file = self.config_dir / "config.toml"
        self.project_config_file = self.config_dir / f"{self.project_name}.toml"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self.uuid = generate_uuid()
        self.reload()

    @classmethod
    def instance(cls, workspace: Optional[Path] = None, project_name: Optional[str] = None) -> "Config":
        if cls._instance is None:
            cls._instance = cls(workspace, project_name or "robot-chat")
        else:
            if workspace is not None or project_name is not None:
                need_reinit = False
                if workspace is not None and cls._instance.base_dir != workspace:
                    need_reinit = True
                if project_name is not None and cls._instance.project_name != project_name:
                    need_reinit = True
                if need_reinit:
                    cls._instance = cls(workspace, project_name or "robot-chat")
        return cls._instance

    def get(self) -> Dict[str, Any]:
        return self._config

    def reload(self) -> None:
        global_cfg = self._load_global()
        project_cfg = self._load_project()
        cfg = dict(project_cfg)
        cfg["robot"] = {
            "uuid": global_cfg.get("uuid") or self.uuid,
            "name": global_cfg.get("name") or f"机器狗-{self.uuid[:4]}",
            "model": global_cfg.get("model") or "agibot-d1",
            "version": global_cfg.get("version") or "0.0.0",
        }
        self._config = cfg

    def save(self, config: Dict[str, Any]) -> None:
        robot_cfg = config.get("robot", {})
        global_cfg = {
            "uuid": robot_cfg.get("uuid") or self.uuid,
            "name": robot_cfg.get("name") or f"机器狗-{self.uuid[:4]}",
            "model": robot_cfg.get("model") or "agibot-d1",
            "version": robot_cfg.get("version") or "0.0.0",
        }
        self._write_toml(self.global_config_file, global_cfg)
        project_cfg = {k: v for k, v in config.items() if k != "robot"}
        self._write_toml(self.project_config_file, project_cfg)
        self.reload()

    def _read_toml(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            with open(path, "rb") as f:
                data = tomli.load(f)
                return data if isinstance(data, dict) else {}
        return {}

    def _write_toml(self, path: Path, data: Dict[str, Any]) -> None:
        with open(path, "wb") as f:
            tomli_w.dump(self._sanitize_for_toml(data), f)

    def _sanitize_for_toml(self, obj: Any) -> Any:
        """递归处理对象，将 None 转换为空字符串，递归处理字典和列表。"""
        if obj is None:
            return ""
        if isinstance(obj, dict):
            return {k: self._sanitize_for_toml(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_for_toml(v) for v in obj]
        return obj

    def _load_global(self) -> Dict[str, Any]:
        exists = self.global_config_file.exists()
        data = self._read_toml(self.global_config_file) if exists else {}
        defaults = {
            "uuid": self.uuid,
            "name": "robot-dog-1",
            "model": "agibot-d1",
            "version": "0.0.0",
        }
        out = {
            "uuid": data.get("uuid") or defaults["uuid"],
            "name": data.get("name") or defaults["name"],
            "model": data.get("model") or defaults["model"],
            "version": data.get("version") or defaults["version"],
        }
        if not exists:
            self._write_toml(self.global_config_file, out)
        return out

    def _load_project(self) -> Dict[str, Any]:
        exists = self.project_config_file.exists()
        if exists:
            return self._read_toml(self.project_config_file)
        defaults = {
            # TODO: 到时候分离手机端和服务端后，将这里的地址修改
            "server": {
                "base_url": f"ws://{SERVER_ADDR}",
                "ws_path": "/api/v1/conversation/connect",
                "control_url": f"ws://{SERVER_ADDR}:9000/api/v1/conversation/connect",
                "business_url": f"ws://{SERVER_ADDR}:9001/api/v1/conversation/connect",
                "audio_upload_url": f"ws://{SERVER_ADDR}:9002/api/v1/conversation/connect",
                "audio_download_url": f"ws://{SERVER_ADDR}:9003/api/v1/conversation/connect",
                "reconnect_interval": 5,
                "heartbeat_interval": 30,
            },
            "sdk": {
                "robot_ip": "127.0.0.1",
                "local_port": 43988,
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration_ms": 20,
                "vad_threshold": 0.015,
                "vad_silence_ms": 800,
                "max_segment_ms": 10000,
                "enable_streaming": True,
                "input_device": None,
            },
            "logging": {
                "level": "INFO",
                "max_file_size_mb": 10,
            },
        }
        self._write_toml(self.project_config_file, defaults)
        return defaults
