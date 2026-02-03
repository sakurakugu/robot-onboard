import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from sparkrobot_common import get_logger


class ProcessController:
    def __init__(self):
        self.logger = get_logger("robot-agent")
        self.process: Optional[subprocess.Popen] = None

    def 启动(self, script_path: str) -> bool:
        try:
            self.logger.info(f"正在启动交互式子进程: {script_path}")

            # 检查脚本文件是否存在
            script_file = Path(script_path)
            if not script_file.exists():
                self.logger.error(f"脚本文件不存在: {script_path}")
                return False

            # 获取 Python 解释器路径
            python_exec = sys.executable
            if not python_exec:
                # 如果 sys.executable 为空，尝试使用 'python3' 或 'python'
                for candidate in ["python3", "python"]:
                    path = shutil.which(candidate)
                    if path:
                        python_exec = path
                        self.logger.warning(f"sys.executable 为空，使用候选 Python: {python_exec}")
                        break

            self.logger.info(f"Python 解释器: {python_exec}")
            self.logger.info(f"脚本路径: {script_path}")

            # 检查脚本是否有执行权限
            if not os.access(script_path, os.R_OK):
                self.logger.error(f"脚本文件不可读: {script_path}")
                return False

            src_dir = Path(script_path).resolve().parents[2]
            self.logger.info(f"设置 PYTHONPATH: {src_dir}")

            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src_dir}:{existing_pythonpath}" if existing_pythonpath else str(src_dir)

            self.process = subprocess.Popen(
                [python_exec, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
                start_new_session=True,
            )
            time.sleep(5)

            if self.process.poll() is not None:
                stderr_output = ""
                if self.process.stderr:
                    stderr_output = self.process.stderr.read().strip()
                if stderr_output:
                    self.logger.error(f"子进程启动失败: {stderr_output}")
                else:
                    self.logger.error("子进程启动失败")
                return False

            self.logger.info("交互式子进程启动成功")
            return True
        except Exception as e:
            import traceback
            self.logger.error(f"启动交互式子进程失败: {e}")
            self.logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False

    def 关闭(self) -> None:
        if self.process and self.process.poll() is None:
            self.logger.info("正在关闭交互式子进程...")
            try:
                if self.process.stdin:
                    self.process.stdin.write("exit\n")
                    self.process.stdin.flush()
                self.process.wait(timeout=5)
            except Exception as e:
                self.logger.warning(f"子进程未正常退出，强制终止: {e}")
                self.process.terminate()
                self.process.wait(timeout=3)
        self.process = None

    def 发送命令(self, command: str) -> bool:
        if not self.process or self.process.poll() is not None:
            self.logger.error("子进程未运行")
            return False

        try:
            if self.process.stdin:
                self.process.stdin.write(f"{command}\n")
                self.process.stdin.flush()
                return True
            self.logger.error("子进程标准输入不可用")
            return False
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            return False
