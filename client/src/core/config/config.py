from pathlib import Path
from typing import Any, Dict, Optional

from .const import DEFAULTS_CONFIG, WORKSPACE_DIR, get_globals_config

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
        cfg["robot"] = get_globals_config(global_cfg)
        self._config = cfg

    def save(self, config: Dict[str, Any]) -> None:
        robot_cfg = config.get("robot", {})
        global_cfg = get_globals_config(robot_cfg)
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
        out = get_globals_config(data)
        if not exists:
            self._write_toml(self.global_config_file, out)
        return out

    def _load_project(self) -> Dict[str, Any]:
        exists = self.project_config_file.exists()
        if exists:
            return self._read_toml(self.project_config_file)
        defaults = DEFAULTS_CONFIG
        self._write_toml(self.project_config_file, defaults)
        return defaults
