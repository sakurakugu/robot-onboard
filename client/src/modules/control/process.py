import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


class ProcessController:
    def __init__(self, logger):
        self.logger = logger
        self.process: Optional[subprocess.Popen] = None

    def start(self, script_path: str) -> bool:
        try:
            self.logger.info(f"正在启动交互式子进程: {script_path}")
            src_dir = Path(script_path).resolve().parents[2]
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src_dir}:{existing_pythonpath}" if existing_pythonpath else str(src_dir)
            self.process = subprocess.Popen(
                [sys.executable, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
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
            self.logger.error(f"启动交互式子进程失败: {e}")
            return False

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.logger.info("正在关闭交互式子进程...")
            try:
                if self.process.stdin:
                    self.process.stdin.write("0\n")
                    self.process.stdin.flush()
                self.process.wait(timeout=5)
            except Exception as e:
                self.logger.warning(f"子进程未正常退出，强制终止: {e}")
                self.process.terminate()
                self.process.wait(timeout=3)
        self.process = None

    def send_command(self, command: str) -> bool:
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
