"""服务安装模块 - 处理 SparkRobotCommon 和 RobotServer 的安装"""

import fnmatch
import os
import tarfile
import zipfile
from pathlib import Path


class 服务安装管理器:
    """服务安装管理器 - 处理 Python 包和服务的安装"""

    def __init__(self, ssh管理器):
        self.ssh = ssh管理器

    def 安装SparkRobotCommon(self, package_ext: str | None = None) -> bool:
        """安装 SparkRobot Common 包"""
        print("\n正在安装 SparkRobot Common...")

        local_common_path = self._获取本地项目路径("sparkrobot-common")
        if local_common_path is None:
            return False

        archive_path = self._打包项目("sparkrobot-common", local_common_path, package_ext)
        if archive_path is None:
            return False

        remote_path = "/home/firefly/sparkrobot/sparkrobot-common"

        # 0. 确保远程目录权限正确 (防止之前用 sudo 运行导致权限归 root)
        self.ssh.执行命令(f"mkdir -p {remote_path}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}", use_sudo=True)

        # 1. 上传文件
        if not self._上传并解压(archive_path, remote_path):
            return False

        # 2. 安装依赖和包
        print("正在安装 sparkrobot-common 依赖...")
        # 使用 python3 -m pip 确保安装到 python3 环境
        cmd_deps = "python3 -m pip install --upgrade pip setuptools wheel uuid6 watchdog"
        success, _, error = self.ssh.执行命令(cmd_deps, use_sudo=True)
        if not success:
            print(f"✗ 安装依赖失败: {error}")
            return False

        print("正在安装 sparkrobot-common...")
        # 使用 -e 安装
        cmd_install = f"python3 -m pip install -e {remote_path}"
        success, _, error = self.ssh.执行命令(cmd_install, use_sudo=True)

        if success:
            print("✓ SparkRobot Common 安装成功")
            return True

        print(f"✗ SparkRobot Common 安装失败: {error}")
        return False

    def 安装RobotServer(self, package_ext: str | None = None) -> bool:
        """安装并启动 Robot Server"""
        if not self.安装SparkRobotCommon(package_ext):
            return False

        print("\n正在安装 Robot Server...")

        local_robot_server_path = self._获取本地项目路径("robot-server")
        if local_robot_server_path is None:
            return False

        archive_path = self._打包项目("robot-server", local_robot_server_path, package_ext)
        if archive_path is None:
            return False

        remote_path = "/home/firefly/sparkrobot/robot-server"

        # 0. 确保远程目录权限正确
        self.ssh.执行命令(f"mkdir -p {remote_path}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}", use_sudo=True)

        # 1. 上传文件
        if not self._上传并解压(archive_path, remote_path):
            return False

        # 2. 安装 robot-server 依赖
        print("正在安装 robot-server 依赖...")
        cmd_install_deps = f"python3 -m pip install {remote_path}"
        success, _, error = self.ssh.执行命令(cmd_install_deps, use_sudo=True)
        if not success:
            print(f"✗ robot-server 依赖安装失败: {error}")
            return False
        print("✓ robot-server 依赖安装完成")

        # 3. 赋予执行权限
        print("正在设置权限...")
        # 尝试检测 install.sh 位置
        install_script = f"{remote_path}/scripts/install.sh"

        # 4. 执行安装脚本
        print("正在运行安装脚本...")
        # 确保脚本有执行权限
        self.ssh.执行命令(f"chmod +x {install_script}")
        success, output, error = self.ssh.执行命令(f"bash {install_script}", use_sudo=True)

        if success:
            print("✓ Robot Server 安装并启动成功")
            print(f"请打开: http://{self.ssh.机器人IP}:8080 进行配置")
            print(output)
            return True

        print(f"✗ 安装失败: {error}")
        return False

    def 安装RobotAgent(self, package_ext: str | None = None) -> bool:
        """安装 Robot Agent"""
        if not self.安装RobotServer(package_ext):
            return False

        print("\n正在解压 Robot Agent...")
        local_robot_agent_path = self._获取本地项目路径("robot-agent")
        if local_robot_agent_path is None:
            return False

        archive_path = self._打包项目("robot-agent", local_robot_agent_path, package_ext)
        if archive_path is None:
            return False

        remote_path = "/home/firefly/sparkrobot/robot-agent"
        if not self._上传并解压(archive_path, remote_path):
            return False

        print("✓ Robot Agent 已解压")
        return True

    def _获取本地项目路径(self, project_name: str) -> Path | None:
        script_dir = Path(__file__).resolve()
        project_root = script_dir.parents[3]
        local_path = project_root / "app" / "robot-agent" / project_name
        if not local_path.exists():
            print(f"✗ 未找到本地 {project_name} 目录: {local_path}")
            return None
        return local_path

    def _解析压缩扩展(self, package_ext: str | None) -> tuple[str, str | None]:
        if not package_ext:
            return ".tar.gz", "gztar"

        value = package_ext.strip().lower()
        if not value.startswith("."):
            value = f".{value}"

        ext_mapping = {
            ".tar.gz": "gztar",
            ".tgz": "gztar",
            ".zip": "zip",
            ".tar": "tar",
            ".tar.bz2": "bztar",
            ".tar.xz": "xztar",
        }
        archive_format = ext_mapping.get(value)
        if archive_format is None:
            return ".tar.gz", "gztar"
        if value == ".tgz":
            return ".tar.gz", archive_format
        return value, archive_format

    def _获取输出目录(self) -> Path:
        script_dir = Path(__file__).resolve()
        project_root = script_dir.parents[3]
        return project_root / "other" / "packages"

    def _是否忽略路径(self, target: Path) -> bool:
        ignore_patterns = [
            "__pycache__", "*.pyc", "*.pyo", "*.pyd",
            "*.egg-info", ".git", ".idea", ".vscode",
            ".DS_Store", "node_modules", "dist", "build",
            ".mypy_cache", ".ruff_cache",
        ]
        for part in target.parts:
            for pattern in ignore_patterns:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _打包项目(self, name: str, source_dir: Path, package_ext: str | None) -> Path | None:
        ext, archive_format = self._解析压缩扩展(package_ext)
        if archive_format is None:
            print("✗ 不支持的压缩格式")
            return None

        output_dir = self._获取输出目录()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{name}{ext}"
        if output_path.exists():
            output_path.unlink()

        if archive_format == "zip":
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(source_dir):
                    root_path = Path(root)
                    dirs[:] = [d for d in dirs if not self._是否忽略路径(root_path / d)]
                    for file_name in files:
                        file_path = root_path / file_name
                        if self._是否忽略路径(file_path):
                            continue
                        arcname = file_path.relative_to(source_dir).as_posix()
                        zip_file.write(file_path, arcname)
            return output_path

        mode_mapping = {
            "gztar": "w:gz",
            "tar": "w",
            "bztar": "w:bz2",
            "xztar": "w:xz",
        }
        mode = mode_mapping.get(archive_format)
        if mode is None:
            print("✗ 不支持的压缩格式")
            return None

        with tarfile.open(output_path, mode) as tar_file:
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                dirs[:] = [d for d in dirs if not self._是否忽略路径(root_path / d)]
                for file_name in files:
                    file_path = root_path / file_name
                    if self._是否忽略路径(file_path):
                        continue
                    arcname = file_path.relative_to(source_dir).as_posix()
                    tar_file.add(file_path, arcname=arcname)
        return output_path

    def _上传并解压(self, archive_path: Path, remote_path: str) -> bool:
        remote_packages_dir = "/home/firefly/sparkrobot/packages"
        self.ssh.执行命令(f"mkdir -p {remote_packages_dir}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_packages_dir}", use_sudo=True)
        self.ssh.执行命令(f"mkdir -p {remote_path}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}", use_sudo=True)

        remote_archive = f"{remote_packages_dir}/{archive_path.name}"
        if not self.ssh.上传文件(str(archive_path), remote_archive):
            return False

        ext = archive_path.name.lower()
        if ext.endswith(".zip"):
            cmd_extract = f"unzip -o {remote_archive} -d {remote_path}"
        elif ext.endswith(".tar.gz") or ext.endswith(".tgz"):
            cmd_extract = f"tar -xzf {remote_archive} -C {remote_path}"
        elif ext.endswith(".tar.bz2"):
            cmd_extract = f"tar -xjf {remote_archive} -C {remote_path}"
        elif ext.endswith(".tar.xz"):
            cmd_extract = f"tar -xJf {remote_archive} -C {remote_path}"
        elif ext.endswith(".tar"):
            cmd_extract = f"tar -xf {remote_archive} -C {remote_path}"
        else:
            print("✗ 不支持的压缩格式")
            return False

        success, _, error = self.ssh.执行命令(cmd_extract, use_sudo=True)
        if not success:
            print(f"✗ 解压失败: {error}")
            return False
        return True
