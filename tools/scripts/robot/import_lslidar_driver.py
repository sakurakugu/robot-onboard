from __future__ import annotations

import argparse
import shutil
from pathlib import Path


脚本文件 = Path(__file__).resolve()
ROBOT_ONBOARD目录 = 脚本文件.parents[3]
仓库根目录 = 脚本文件.parents[5]
默认工作空间目录 = ROBOT_ONBOARD目录 / "robot-ros"
默认厂商源码目录 = (
    仓库根目录
    / "other"
    / "2D激光雷达资料"
    / "N10系列激光雷达附送资料"
    / "N10系列雷达客户资料V5.0_20240822"
    / "2.ROS2_SDK"
    / "LSLIDAR_X_ROS2-20240228"
    / "src"
)
支持的包名 = ("lslidar_driver", "lslidar_msgs")


def 解析命令行参数() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="把本地资料目录中的镭神 N10P ROS2 驱动导入到 robot-ros 工作空间。",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=默认厂商源码目录,
        help=f"厂商 ROS2 源码目录，默认: {默认厂商源码目录}",
    )
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=默认工作空间目录,
        help=f"目标 robot-ros 工作空间目录，默认: {默认工作空间目录}",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        choices=支持的包名,
        default=list(支持的包名),
        help="指定要导入的包，默认同时导入 lslidar_driver 和 lslidar_msgs。",
    )
    return parser.parse_args()


def 校验目标目录(target_dir: Path, workspace_src_dir: Path) -> None:
    """确保删除或覆盖动作只发生在 robot-ros/src 内。"""
    resolved_target = target_dir.resolve()
    resolved_workspace_src = workspace_src_dir.resolve()
    try:
        resolved_target.relative_to(resolved_workspace_src)
    except ValueError as exc:
        raise ValueError(f"目标目录不在工作空间 src 下: {target_dir}") from exc


def 校验来源包(source_dir: Path, package_name: str) -> Path:
    """校验厂商源码包是否存在。"""
    package_dir = source_dir / package_name
    if not package_dir.exists():
        raise FileNotFoundError(f"找不到来源包目录: {package_dir}")
    if not (package_dir / "package.xml").exists():
        raise FileNotFoundError(f"来源包缺少 package.xml: {package_dir}")
    return package_dir


def 导入单个包(source_dir: Path, workspace_src_dir: Path, package_name: str) -> Path:
    """导入单个 ROS2 包。"""
    source_package_dir = 校验来源包(source_dir, package_name)
    target_package_dir = workspace_src_dir / package_name
    校验目标目录(target_package_dir, workspace_src_dir)

    if target_package_dir.exists():
        print(f"覆盖已有目录: {target_package_dir}")
        shutil.rmtree(target_package_dir)

    shutil.copytree(source_package_dir, target_package_dir)
    print(f"已导入 {package_name}: {target_package_dir}")
    return target_package_dir


def main() -> int:
    """执行导入流程。"""
    args = 解析命令行参数()
    source_dir = args.source_dir.expanduser().resolve()
    workspace_dir = args.workspace_dir.expanduser().resolve()
    workspace_src_dir = workspace_dir / "src"

    if not source_dir.exists():
        print(f"找不到厂商源码目录: {source_dir}")
        return 1

    workspace_src_dir.mkdir(parents=True, exist_ok=True)

    print("开始导入 N10P ROS2 厂商驱动")
    print(f"来源目录: {source_dir}")
    print(f"目标目录: {workspace_src_dir}")

    imported_dirs: list[Path] = []
    for package_name in args.packages:
        imported_dirs.append(导入单个包(source_dir, workspace_src_dir, package_name))

    print("导入完成")
    for imported_dir in imported_dirs:
        print(f"- {imported_dir}")
    print("下一步可在 robot-ros 目录执行: colcon build --symlink-install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
