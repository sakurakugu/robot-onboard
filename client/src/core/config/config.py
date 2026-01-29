from pathlib import Path
from typing import Any, Dict, Optional

from .const import APP_NAME, DEFAULTS_CONFIG, WORKSPACE_DIR, get_globals_config

try:
    import tomli
    import tomli_w
except ImportError:
    raise RuntimeError("tomli 或 tomli_w 没有安装") from None


class Config:
    _instance: Optional["Config"] = None

    def __init__(self, workspace: Optional[Path] = None, project_name: str = APP_NAME):
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
            cls._instance = cls(workspace, project_name or "robot-agent")
        else:
            if workspace is not None or project_name is not None:
                need_reinit = False
                if workspace is not None and cls._instance.base_dir != workspace:
                    need_reinit = True
                if project_name is not None and cls._instance.project_name != project_name:
                    need_reinit = True
                if need_reinit:
                    cls._instance = cls(workspace, project_name or "robot-agent")
        return cls._instance

    def get(self) -> Dict[str, Any]:
        return self._config

    def reload(self) -> None:
        global_cfg = self._加载全局配置()
        project_cfg = self._加载项目配置()
        cfg = dict(project_cfg)
        cfg["robot"] = get_globals_config(global_cfg)
        self._config = cfg

    def save(self, config: Dict[str, Any]) -> None:
        robot_cfg = config.get("robot", {})
        global_cfg = get_globals_config(robot_cfg)
        self._写入TOML(self.global_config_file, global_cfg)
        project_cfg = {k: v for k, v in config.items() if k != "robot"}
        self._写入TOML(self.project_config_file, project_cfg)
        self.reload()

    def _读取TOML(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            with open(path, "rb") as f:
                data = tomli.load(f)
                return data if isinstance(data, dict) else {}
        return {}

    def _写入TOML(self, path: Path, data: Dict[str, Any]) -> None:
        with open(path, "wb") as f:
            tomli_w.dump(self._无害化TOML数据(data), f)

    def _无害化TOML数据(self, obj: Any) -> Any:
        """递归处理对象，将 None 转换为空字符串，递归处理字典和列表。"""
        if obj is None:
            return ""
        if isinstance(obj, dict):
            return {k: self._无害化TOML数据(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._无害化TOML数据(v) for v in obj]
        return obj

    def _加载全局配置(self) -> Dict[str, Any]:
        exists = self.global_config_file.exists()
        data = self._读取TOML(self.global_config_file) if exists else {}
        out = get_globals_config(data)
        if not exists:
            self._写入TOML(self.global_config_file, out)
        return out

    def _加载项目配置(self) -> Dict[str, Any]:
        exists = self.project_config_file.exists()
        if exists:
            return self._读取TOML(self.project_config_file)
        defaults = DEFAULTS_CONFIG
        self._写入TOML(self.project_config_file, defaults)
        return defaults
