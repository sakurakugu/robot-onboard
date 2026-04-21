"""本体套件打包工具"""

import fnmatch
import json
import os
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = PROJECT_ROOT / "dist" / "packages"

忽略模式 = [
    "__pycache__", "*.pyc", "*.pyo", "*.pyd",
    "*.egg-info", ".git", ".idea", ".vscode",
    ".DS_Store", "node_modules", "dist", "build", "install", "log",
    ".mypy_cache", ".ruff_cache",
]


def 解析压缩格式(raw_value: str) -> tuple[str, str]:
    """解析压缩格式，返回 (打包格式, 文件扩展名)"""
    value = raw_value.strip().lower()
    if value.startswith("."):
        value = value.lstrip(".")

    format_mapping = {
        "tar.gz": ("gztar", ".tar.gz"),
        "tgz": ("gztar", ".tar.gz"),
        "gztar": ("gztar", ".tar.gz"),
        "zip": ("zip", ".zip"),
        "tar": ("tar", ".tar"),
        "bztar": ("bztar", ".tar.bz2"),
        "tar.bz2": ("bztar", ".tar.bz2"),
        "xztar": ("xztar", ".tar.xz"),
        "tar.xz": ("xztar", ".tar.xz"),
    }

    if not value:
        return "gztar", ".tar.gz"

    if value in format_mapping:
        return format_mapping[value]

    print("[ERR] 未识别的压缩格式，已使用默认 tar.gz")
    return "gztar", ".tar.gz"


def 是否忽略路径(target: Path) -> bool:
    """判断路径是否应在打包时跳过"""
    for part in target.parts:
        for pattern in 忽略模式:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def 写入压缩包(output_path: Path, source_dir: Path, archive_format: str) -> None:
    """将目录写入目标压缩包"""
    if output_path.exists():
        output_path.unlink()

    if archive_format == "zip":
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                dirs[:] = [d for d in dirs if not 是否忽略路径(root_path / d)]
                for file_name in files:
                    file_path = root_path / file_name
                    if 是否忽略路径(file_path):
                        continue
                    arcname = file_path.relative_to(source_dir).as_posix()
                    zip_file.write(file_path, arcname)
        return

    mode_mapping: dict[str, Literal["w", "w:gz", "w:bz2", "w:xz"]] = {
        "gztar": "w:gz",
        "tar": "w",
        "bztar": "w:bz2",
        "xztar": "w:xz",
    }
    mode = mode_mapping.get(archive_format)
    if mode is None:
        raise ValueError(f"不支持的压缩格式: {archive_format}")

    with tarfile.open(output_path, mode) as tar_file:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not 是否忽略路径(root_path / d)]
            for file_name in files:
                file_path = root_path / file_name
                if 是否忽略路径(file_path):
                    continue
                arcname = file_path.relative_to(source_dir).as_posix()
                tar_file.add(file_path, arcname=arcname)


def 获取打包输出目录() -> Path:
    """返回打包产物目录"""
    return PACKAGES_DIR


def 打包单个项目(name: str, source_dir: Path, package_ext: str | None = None) -> Path | None:
    """按指定扩展名打包单个项目"""
    if not source_dir.exists():
        print(f"[ERR] 找不到目录: {source_dir}")
        return None

    archive_format, ext = 解析压缩格式(package_ext or "tar.gz")
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PACKAGES_DIR / f"{name}{ext}"
    写入压缩包(output_path, source_dir, archive_format)
    print(f"✓ 已生成: {output_path}")
    return output_path


def 获取本体项目列表() -> list[tuple[str, Path]]:
    """返回本体相关项目目录。"""
    return [
        ("sparkrobot-common", PROJECT_ROOT / "sparkrobot-common"),
        ("robot-server", PROJECT_ROOT / "robot-server"),
        ("robot-agent", PROJECT_ROOT / "robot-agent"),
        ("robot-runtime", PROJECT_ROOT / "robot-runtime"),
        ("robot-ros", PROJECT_ROOT / "robot-ros"),
    ]


def 获取本体项目映射() -> dict[str, Path]:
    """返回项目名称到目录的映射。"""
    return {name: path for name, path in 获取本体项目列表()}


def 获取默认打包项目名称列表() -> list[str]:
    """返回默认需要打包的项目名称列表。"""
    return [name for name, _ in 获取本体项目列表()]


def 打包项目集合(project_names: list[str], archive_format: str, ext: str) -> list[Path]:
    """按项目名称列表打包项目。"""
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    project_mapping = 获取本体项目映射()

    for name in project_names:
        path = project_mapping.get(name)
        if path is None:
            print(f"[ERR] 未知项目: {name}")
            continue
        if not path.exists():
            print(f"[ERR] 找不到目录: {path}")
            continue
        output_path = PACKAGES_DIR / f"{name}{ext}"
        写入压缩包(output_path, path, archive_format)
        outputs.append(output_path)
        print(f"[OK] 已生成: {output_path}")

    return outputs


def 打包整包(project_names: list[str], archive_format: str, ext: str) -> Path | None:
    """将多个项目子包打成一个 full 整包。"""
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PACKAGES_DIR / f"robot-full{ext}"
    project_mapping = 获取本体项目映射()

    with tempfile.TemporaryDirectory(prefix="robot-full-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        packages_dir = temp_dir / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)

        bundled_names: list[str] = []
        for name in project_names:
            path = project_mapping.get(name)
            if path is None:
                print(f"[ERR] 未知项目: {name}")
                continue
            if not path.exists():
                print(f"[ERR] 找不到目录: {path}")
                continue
            child_output = packages_dir / f"{name}.tar.gz"
            写入压缩包(child_output, path, "gztar")
            bundled_names.append(name)

        if not bundled_names:
            return None

        manifest = {
            "bundle": "robot-full",
            "projects": bundled_names,
            "package_archive_ext": ".tar.gz",
            "bundle_archive_ext": ext,
        }
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        写入压缩包(output_path, temp_dir, archive_format)

    print(f"[OK] 已生成: {output_path}")
    return output_path


def 获取robot_agent项目列表() -> list[tuple[str, Path]]:
    """兼容旧调用，返回当前本体项目目录。"""
    return 获取本体项目列表()


def 打包robot_agent套件(archive_format: str, ext: str) -> list[Path]:
    """兼容旧调用，打包当前本体套件。"""
    return 打包项目集合(获取默认打包项目名称列表(), archive_format, ext)


def 执行打包流程(
    open_explorer: bool = True,
    require_prompt: bool = True,
    project_names: list[str] | None = None,
    title: str = "打包本体套件",
    package_format: str = "tar.gz",
) -> tuple[str, str, list[Path]]:
    """执行本体套件打包流程。"""
    print("\n" + "-" * 50)
    print(title)
    print("-" * 50)

    if require_prompt:
        print("支持格式: tar.gz(默认), zip, tar, tar.bz2, tar.xz")
        raw_format = input("请输入压缩格式 (回车默认 tar.gz): ")
        archive_format, ext = 解析压缩格式(raw_format)
    else:
        archive_format, ext = 解析压缩格式(package_format)

    target_names = project_names or 获取默认打包项目名称列表()
    if len(target_names) > 1:
        full_output = 打包整包(target_names, archive_format, ext)
        outputs = [full_output] if full_output else []
    else:
        outputs = 打包项目集合(target_names, archive_format, ext)
    if outputs:
        print("\n" + "=" * 50)
        print("[OK] 打包完成")
        print("=" * 50)
        if open_explorer and hasattr(os, "startfile"):
            os.startfile(str(PACKAGES_DIR))
    else:
        print("\n" + "=" * 50)
        print("[ERR] 打包失败")
        print("=" * 50)
    return archive_format, ext, outputs
