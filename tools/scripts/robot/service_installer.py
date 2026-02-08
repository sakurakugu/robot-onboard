"""服务安装模块 - 处理 SparkRobotCommon 和 RobotServer 的安装"""

import os


class 服务安装管理器:
    """服务安装管理器 - 处理 Python 包和服务的安装"""

    def __init__(self, ssh管理器):
        self.ssh = ssh管理器

    def 安装SparkRobotCommon(self) -> bool:
        """安装 SparkRobot Common 包

        Returns:
            成功返回True，失败返回False
        """
        print("\n正在安装 SparkRobot Common...")

        # 定位本地 sparkrobot-common 目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # 调整路径：从 tools/scripts/robot 回退 3 层到 root，然后进入 app/robot-agent/sparkrobot-common
        local_common_path = os.path.join(script_dir, "..", "..", "..", "app", "robot-agent", "sparkrobot-common")
        local_common_path = os.path.normpath(local_common_path)

        if not os.path.exists(local_common_path):
            print(f"✗ 未找到本地 sparkrobot-common 目录: {local_common_path}")
            return False

        remote_path = "/home/firefly/sparkrobot/sparkrobot-common"

        # 0. 确保远程目录权限正确 (防止之前用 sudo 运行导致权限归 root)
        self.ssh.执行命令(f"mkdir -p {remote_path}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}", use_sudo=True)

        # 1. 上传文件
        print(f"正在将 {local_common_path} 上传到 {remote_path}...")
        if not self.ssh.上传目录(local_common_path, remote_path):
            return False

        # 2. 安装依赖和包
        print("正在安装 sparkrobot-common 依赖...")
        # 使用 python3 -m pip 确保安装到 python3 环境
        cmd_deps = "python3 -m pip install --upgrade pip setuptools wheel uuid6 watchdog"
        success, output, error = self.ssh.执行命令(cmd_deps, use_sudo=True)
        if not success:
            print(f"✗ 安装依赖失败: {error}")
            return False

        print("正在安装 sparkrobot-common...")
        # 使用 -e 安装
        cmd_install = f"python3 -m pip install -e {remote_path}"
        success, output, error = self.ssh.执行命令(cmd_install, use_sudo=True)

        if success:
            print("✓ SparkRobot Common 安装成功")
            return True
        else:
            print(f"✗ SparkRobot Common 安装失败: {error}")
            return False

    def 安装RobotServer(self) -> bool:
        """安装并启动 Robot Server

        Returns:
            成功返回True，失败返回False
        """
        # 先安装 sparkrobot-common
        if not self.安装SparkRobotCommon():
            return False

        print("\n正在安装 Robot Server...")

        # 定位本地 robot-server 目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # 调整路径：从 tools/scripts/robot 回退 3 层到 root，然后进入 app/robot-agent/robot-server
        local_robot_server_path = os.path.join(script_dir, "..", "..", "..", "app", "robot-agent", "robot-server")
        local_robot_server_path = os.path.normpath(local_robot_server_path)

        if not os.path.exists(local_robot_server_path):
            print(f"✗ 未找到本地 robot-server 目录: {local_robot_server_path}")
            return False

        remote_path = "/home/firefly/sparkrobot/robot-server"

        # 0. 确保远程目录权限正确
        self.ssh.执行命令(f"mkdir -p {remote_path}")
        self.ssh.执行命令(f"chown -R {self.ssh.用户名}:{self.ssh.用户名} {remote_path}", use_sudo=True)

        # 1. 上传文件
        print(f"正在将 {local_robot_server_path} 上传到 {remote_path}...")
        if not self.ssh.上传目录(local_robot_server_path, remote_path):
            return False

        # 2. 安装 robot-server 依赖
        print("正在安装 robot-server 依赖...")
        cmd_install_deps = f"python3 -m pip install {remote_path}"
        success, output, error = self.ssh.执行命令(cmd_install_deps, use_sudo=True)
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
        else:
            print(f"✗ 安装失败: {error}")
            return False
