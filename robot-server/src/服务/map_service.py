from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from ruamel.yaml import YAML

from .config_service import 获取配置管理器单例


@dataclass(slots=True)
class 地图文件记录:
    id: str
    name: str
    yaml_path: Path
    image_path: Path
    image_format: str
    updated_at: str


class 地图服务:
    def __init__(self) -> None:
        self._yaml = YAML(typ="safe")

    def 获取地图目录(self) -> Path:
        配置管理器 = 获取配置管理器单例()
        raw_path = 配置管理器.获取("mapping.map_save_dir")
        map_dir = Path(str(raw_path or "")).expanduser()
        if not str(map_dir).strip():
            raise ValueError("未配置 mapping.map_save_dir")
        return map_dir.resolve()

    def 获取地图列表(self) -> list[dict[str, str]]:
        地图目录 = self.获取地图目录()
        if not 地图目录.exists():
            return []

        结果: list[dict[str, str]] = []
        for yaml_path in sorted(地图目录.rglob("*.yaml")):
            if not yaml_path.is_file():
                continue
            记录 = self._读取地图记录(地图目录, yaml_path)
            if 记录 is None:
                continue
            结果.append(
                {
                    "id": 记录.id,
                    "name": 记录.name,
                    "yaml_path": str(记录.yaml_path),
                    "image_path": str(记录.image_path),
                    "image_format": 记录.image_format,
                    "updated_at": 记录.updated_at,
                }
            )

        结果.sort(key=lambda item: item["updated_at"], reverse=True)
        return 结果

    def 打包地图(self, map_id: str) -> tuple[bytes, str]:
        地图目录 = self.获取地图目录()
        记录 = self._查找地图记录(地图目录, map_id)

        output = BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            yaml_arcname = self._计算归档相对路径(地图目录, 记录.yaml_path)
            image_arcname = self._计算归档相对路径(地图目录, 记录.image_path)
            zip_file.write(记录.yaml_path, arcname=yaml_arcname)
            zip_file.write(记录.image_path, arcname=image_arcname)

        return output.getvalue(), f"{记录.name}.zip"

    def _查找地图记录(self, 地图目录: Path, map_id: str) -> 地图文件记录:
        normalized_id = map_id.strip().replace("\\", "/")
        if not normalized_id:
            raise ValueError("地图 ID 不能为空")

        yaml_path = (地图目录 / normalized_id).resolve()
        if 地图目录 not in yaml_path.parents or yaml_path.suffix.lower() != ".yaml":
            raise ValueError("地图 ID 不合法")
        if not yaml_path.exists() or not yaml_path.is_file():
            raise FileNotFoundError("未找到指定地图")

        记录 = self._读取地图记录(地图目录, yaml_path)
        if 记录 is None:
            raise FileNotFoundError("未找到指定地图")
        return 记录

    def _读取地图记录(self, 地图目录: Path, yaml_path: Path) -> 地图文件记录 | None:
        try:
            yaml_data = self._yaml.load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(yaml_data, dict):
            return None

        image_field = yaml_data.get("image")
        if not isinstance(image_field, str) or not image_field.strip():
            return None

        image_path = (yaml_path.parent / image_field).expanduser().resolve()
        if not image_path.exists() or not image_path.is_file():
            return None
        if 地图目录 not in image_path.parents:
            return None

        yaml_stat = yaml_path.stat()
        image_stat = image_path.stat()
        updated_at = datetime.fromtimestamp(max(yaml_stat.st_mtime, image_stat.st_mtime)).isoformat()
        return 地图文件记录(
            id=self._计算归档相对路径(地图目录, yaml_path),
            name=yaml_path.stem,
            yaml_path=yaml_path,
            image_path=image_path,
            image_format=image_path.suffix.lower().lstrip(".") or "unknown",
            updated_at=updated_at,
        )

    def _计算归档相对路径(self, 地图目录: Path, file_path: Path) -> str:
        return file_path.relative_to(地图目录).as_posix()


_地图服务单例: 地图服务 | None = None


def 获取地图服务单例() -> 地图服务:
    global _地图服务单例
    if _地图服务单例 is None:
        _地图服务单例 = 地图服务()
    return _地图服务单例
