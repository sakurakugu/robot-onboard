"""服务安装模块。"""

from pathlib import Path

from .package_builder import 打包单个项目

ROSDISTRO_INDEX_URL = "https://mirrors.tuna.tsinghua.edu.cn/rosdistro/index-v4.yaml"
ROSDEP_SOURCES_LIST_CONTENT = """# os-specific listings first
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/osx-homebrew.yaml osx

# generic
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/base.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/python.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/ruby.yaml
"""


class 服务安装管理器:
    """服务安装管理器。"""

    def __init__(self, ssh管理器):
        self.ssh = ssh管理器

    def 安装SparkRobotCommon(self, package_ext: str | None = None) -> bool:
        """安装 SparkRobot Common 包。"""
        print("\n正在安装 SparkRobot Common...")

        local_common_path = self._获取本地项目路径("sparkrobot-common")
        if local_common_path is None:
            return False

        archive_path = self._打包项目("sparkrobot-common", local_common_path, package_ext)
        if archive_path is None:
            return False

        remote_path = "/home/firefly/sparkrobot/sparkrobot-common"
        if not self._准备远程目录(remote_path):
            return False
        if not self._上传并解压(archive_path, remote_path):
            return False

        print("正在安装 sparkrobot-common 依赖...")
        cmd_install_deps = "python3 -m pip install uuid6 watchdog"
        success, _, error = self.ssh.执行命令(cmd_install_deps, use_sudo=True)
        if not success:
            print(f"✗ 安装依赖失败: {error}")
            return False

        print("正在安装 sparkrobot-common...")
        cmd_install = f"python3 -m pip install --no-deps -e {remote_path}"
        success, _, error = self.ssh.执行命令(cmd_install, use_sudo=True)
        if success:
            print("✓ SparkRobot Common 安装成功")
            return True

        print(f"✗ SparkRobot Common 安装失败: {error}")
        return False

    def 安装RobotServer(self, package_ext: str | None = None) -> bool:
        """安装 Robot Server。"""
        if not self.安装SparkRobotCommon(package_ext):
            return False
        return self._安装Python服务项目(
            project_name="robot-server",
            display_name="Robot Server",
            remote_path="/home/firefly/sparkrobot/robot-server",
            package_ext=package_ext,
            success_tip=f"请打开: http://{self.ssh.机器人IP}:8080 进行配置",
            service_name="sparkrobot-server.service",
            occupied_ports=[8080],
        )

    def 安装RobotAgent(self, package_ext: str | None = None) -> bool:
        """安装 Robot Agent。"""
        if not self.安装SparkRobotCommon(package_ext):
            return False
        if not self._安装Python服务项目(
            project_name="robot-server",
            display_name="Robot Server",
            remote_path="/home/firefly/sparkrobot/robot-server",
            package_ext=package_ext,
            success_tip=f"请打开: http://{self.ssh.机器人IP}:8080 进行配置",
            service_name="sparkrobot-server.service",
            occupied_ports=[8080],
        ):
            return False
        return self._安装Python服务项目(
            project_name="robot-agent",
            display_name="Robot Agent",
            remote_path="/home/firefly/sparkrobot/robot-agent",
            package_ext=package_ext,
            service_name="sparkrobot-agent.service",
        )

    def 安装RobotRuntime(self, package_ext: str | None = None) -> bool:
        """安装 Robot Runtime。"""
        if not self.安装SparkRobotCommon(package_ext):
            return False
        return self._安装Python服务项目(
            project_name="robot-runtime",
            display_name="Robot Runtime",
            remote_path="/home/firefly/sparkrobot/robot-runtime",
            package_ext=package_ext,
        )

    def 安装RobotRos工作区(self, package_ext: str | None = None) -> bool:
        """安装并构建 robot-ros 工作区。"""
        print("\n正在安装 robot-ros 工作区...")

        local_robot_ros_path = self._获取本地项目路径("robot-ros")
        if local_robot_ros_path is None:
            return False

        archive_path = self._打包项目("robot-ros", local_robot_ros_path, package_ext)
        if archive_path is None:
            return False

        remote_path = "/home/firefly/sparkrobot/robot-ros"
        if not self._准备远程目录(remote_path):
            return False

        self.ssh.执行命令(f"rm -rf {remote_path}/build {remote_path}/install {remote_path}/log")
        if not self._上传并解压(archive_path, remote_path):
            return False

        print("正在检查 ROS2 Humble 环境...")
        check_ros_cmd = "bash -lc 'test -f /opt/ros/humble/setup.bash'"
        success, _, _ = self.ssh.执行命令(check_ros_cmd)
        if not success:
            print("✗ 未检测到 /opt/ros/humble/setup.bash，请先在目标机器安装 ROS2 Humble")
            return False

        if not self._确保rosdep已初始化():
            return False

        print("正在安装 robot-ros 依赖...")
        rosdep_cmd = (
            "bash -lc '"
            f"export HOME=/home/{self.ssh.用户名} && "
            f"export ROS_HOME=/home/{self.ssh.用户名}/.ros && "
            f"source /opt/ros/humble/setup.bash && "
            f"export ROSDISTRO_INDEX_URL={ROSDISTRO_INDEX_URL} && "
            f"cd {remote_path} && "
            "rosdep install --from-paths src --ignore-src -r -y"
            "'"
        )
        success, output, error = self.ssh.执行命令(rosdep_cmd, use_sudo=True)
        if not success:
            details = self._构建错误详情(output, error)
            print(f"✗ robot-ros 依赖安装失败: {details}")
            print("提示: 如果缺少 lslidar_driver / lslidar_msgs，请先在本地导入厂商驱动后再重试")
            return False
        print("✓ robot-ros 依赖安装完成")

        print("正在构建 robot-ros 工作区...")
        build_cmd = (
            "bash -lc '"
            f"source /opt/ros/humble/setup.bash && "
            f"cd {remote_path} && "
            "colcon build"
            "'"
        )
        success, output, error = self.ssh.执行命令(build_cmd)
        if not success:
            details = self._构建错误详情(output, error)
            print(f"✗ robot-ros 工作区构建失败: {details}")
            return False

        print("✓ robot-ros 工作区构建成功")
        return True

    def 安装本体全套(self, package_ext: str | None = None) -> bool:
        """安装本体全套软件。"""
        print("\n正在安装本体全套软件...")
        if not self.安装SparkRobotCommon(package_ext):
            return False
        if not self._安装Python服务项目(
            project_name="robot-server",
            display_name="Robot Server",
            remote_path="/home/firefly/sparkrobot/robot-server",
            package_ext=package_ext,
            success_tip=f"请打开: http://{self.ssh.机器人IP}:8080 进行配置",
            service_name="sparkrobot-server.service",
            occupied_ports=[8080],
        ):
            return False
        if not self._安装Python服务项目(
            project_name="robot-agent",
            display_name="Robot Agent",
            remote_path="/home/firefly/sparkrobot/robot-agent",
            package_ext=package_ext,
            service_name="sparkrobot-agent.service",
        ):
            return False
        if not self.安装RobotRos工作区(package_ext):
            return False
        if not self._安装Python服务项目(
            project_name="robot-runtime",
            display_name="Robot Runtime",
            remote_path="/home/firefly/sparkrobot/robot-runtime",
            package_ext=package_ext,
            service_name="sparkrobot-runtime.service",
        ):
            return False

        print("✓ 本体全套软件安装完成")
        return True

    def _确保rosdep已初始化(self) -> bool:
        """确保目标机器的 rosdep 已初始化。"""
        print("正在检查 rosdep 初始化状态...")
        check_cmd = "bash -lc 'test -f /etc/ros/rosdep/sources.list.d/20-default.list'"
        success, _, _ = self.ssh.执行命令(check_cmd)
        if success:
            print("✓ rosdep 已初始化")
        else:
            print("未检测到 rosdep 默认源，正在直接写入镜像配置...")
            init_cmd = "bash -lc 'mkdir -p /etc/ros/rosdep/sources.list.d'"
            success, output, error = self.ssh.执行命令(init_cmd, use_sudo=True)
            if not success:
                details = self._构建错误详情(output, error)
                print(f"✗ 创建 rosdep 配置目录失败: {details}")
                return False

        print("正在切换 rosdep 源到镜像...")
        success = self.ssh.写入配置文件(
            ROSDEP_SOURCES_LIST_CONTENT,
            "/etc/ros/rosdep/sources.list.d/20-default.list",
            "rosdep 源配置",
        )
        if not success:
            print("✗ 写入 rosdep 镜像源失败")
            return False

        print("正在更新 rosdep 源...")
        update_cmd = f"bash -lc 'export ROSDISTRO_INDEX_URL={ROSDISTRO_INDEX_URL} && rosdep update'"
        success, output, error = self.ssh.执行命令(update_cmd)
        if not success:
            details = self._构建错误详情(output, error)
            print(f"✗ rosdep update 失败: {details}")
            return False

        print("✓ rosdep 初始化完成")
        return True

    def _安装Python服务项目(
        self,
        project_name: str,
        display_name: str,
        remote_path: str,
        package_ext: str | None,
        success_tip: str | None = None,
        service_name: str | None = None,
        occupied_ports: list[int] | None = None,
    ) -> bool:
        """安装并启动 Python 服务项目。"""
        print(f"\n正在安装 {display_name}...")

        local_project_path = self._获取本地项目路径(project_name)
        if local_project_path is None:
            return False

        archive_path = self._打包项目(project_name, local_project_path, package_ext)
        if archive_path is None:
            return False

        if not self._准备远程目录(remote_path):
            return False
        if not self._上传并解压(archive_path, remote_path):
            return False

        print(f"正在安装 {project_name} 依赖...")
        cmd_install_deps = f"python3 -m pip install {remote_path}"
        success, _, error = self.ssh.执行命令(cmd_install_deps, use_sudo=True)
        if not success:
            print(f"✗ {project_name} 依赖安装失败: {error}")
            return False
        print(f"✓ {project_name} 依赖安装完成")

        install_script = f"{remote_path}/scripts/install.sh"
        print("正在设置权限...")
        self.ssh.执行命令(f"chmod +x {install_script}")

        print("正在运行安装脚本...")
        success, output, error = self.ssh.执行命令(f"bash {install_script}", use_sudo=True)
        if not success:
            details = self._构建错误详情(output, error)
            if service_name:
                diagnosis = self._收集服务诊断信息(service_name, occupied_ports)
                if diagnosis:
                    details = f"{details}\n\n{diagnosis}"
            print(f"✗ 安装失败: {details}")
            return False

        print(f"✓ {display_name} 安装并启动成功")
        if success_tip:
            print(success_tip)
        if output.strip():
            print(output)
        return True

    def _获取本地项目路径(self, project_name: str) -> Path | None:
        script_dir = Path(__file__).resolve()
        project_root = script_dir.parents[3]
        local_path = project_root / project_name
        if not local_path.exists():
            print(f"✗ 未找到本地 {project_name} 目录: {local_path}")
            return None
        return local_path

    def _打包项目(self, name: str, source_dir: Path, package_ext: str | None) -> Path | None:
        return 打包单个项目(name, source_dir, package_ext)

    def _准备远程目录(self, remote_path: str) -> bool:
        remote_workspace_dir = "/home/firefly/sparkrobot"
        success, _, error = self.ssh.执行命令(f"mkdir -p {remote_workspace_dir}")
        if not success:
            print(f"✗ 创建远程工作目录失败: {error}")
            return False

        success, _, error = self.ssh.执行命令(
            f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_workspace_dir}",
            use_sudo=True,
        )
        if not success:
            print(f"✗ 修正远程工作目录权限失败: {error}")
            return False

        success, _, error = self.ssh.执行命令(f"mkdir -p {remote_path}")
        if not success:
            print(f"✗ 创建远程项目目录失败: {error}")
            return False

        success, _, error = self.ssh.执行命令(
            f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}",
            use_sudo=True,
        )
        if not success:
            print(f"✗ 修正远程项目目录权限失败: {error}")
            return False
        return True

    def _上传并解压(self, archive_path: Path, remote_path: str) -> bool:
        remote_packages_dir = "/home/firefly/sparkrobot/packages"

        success, _, error = self.ssh.执行命令(f"mkdir -p {remote_packages_dir}")
        if not success:
            print(f"✗ 创建远程包目录失败: {error}")
            return False

        success, _, error = self.ssh.执行命令(
            f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_packages_dir}",
            use_sudo=True,
        )
        if not success:
            print(f"✗ 修正远程包目录权限失败: {error}")
            return False

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

        success, _, error = self.ssh.执行命令(
            f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}",
            use_sudo=True,
        )
        if not success:
            print(f"✗ 修正解压后目录权限失败: {error}")
            return False
        return True

    def _构建错误详情(self, output: str, error: str) -> str:
        """构建更可读的错误详情。"""
        details = (error or "").strip() or (output or "").strip()
        if not details:
            return "未返回错误信息"
        return details

    def _收集服务诊断信息(self, service_name: str, occupied_ports: list[int] | None = None) -> str:
        diagnostics: list[str] = []

        status_cmd = f"systemctl status {service_name} --no-pager -l"
        success, output, error = self.ssh.执行命令(status_cmd, use_sudo=True)
        status_text = (output or error).strip()
        if success or status_text:
            diagnostics.append(f"[systemctl status]\n{status_text}")

        journal_cmd = f"journalctl -u {service_name} -n 50 --no-pager -l"
        success, output, error = self.ssh.执行命令(journal_cmd, use_sudo=True)
        journal_text = (output or error).strip()
        if success or journal_text:
            diagnostics.append(f"[journalctl]\n{journal_text}")

        if occupied_ports:
            port_lines: list[str] = []
            for port in occupied_ports:
                tcp_cmd = f"ss -ltnp | grep ':{port} ' || true"
                _, output, error = self.ssh.执行命令(tcp_cmd, use_sudo=True)
                tcp_text = (output or error).strip()
                if tcp_text:
                    port_lines.append(f"TCP {port}:\n{tcp_text}")

                udp_cmd = f"ss -lunp | grep ':{port} ' || true"
                _, output, error = self.ssh.执行命令(udp_cmd, use_sudo=True)
                udp_text = (output or error).strip()
                if udp_text:
                    port_lines.append(f"UDP {port}:\n{udp_text}")

            if port_lines:
                diagnostics.append("[端口占用]\n" + "\n".join(port_lines))

        return "\n\n".join(item for item in diagnostics if item.strip())
