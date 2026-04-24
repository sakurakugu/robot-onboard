from __future__ import annotations

import asyncio
import inspect
import os
import signal
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, BinaryIO, Callable

from sparkrobot_common import get_logger

from .ros_workspace_service import ROS启动计划, ROS工作空间服务

logger = get_logger("robot-runtime")

退出回调类型 = Callable[[str, int, bool], Awaitable[None] | None]


class ROS进程服务错误(RuntimeError):
    """ROS 进程服务错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ROS进程摘要:
    """ROS 进程摘要。"""

    名称: str
    包名: str
    启动文件: str
    pid: int | None
    命令: str
    工作目录: str
    日志文件: str
    启动时间: str
    运行中: bool

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "name": self.名称,
            "package": self.包名,
            "launch_file": self.启动文件,
            "pid": self.pid,
            "command": self.命令,
            "cwd": self.工作目录,
            "log_file": self.日志文件,
            "started_at": self.启动时间,
            "running": self.运行中,
        }


@dataclass
class ROS进程记录:
    """运行中的 ROS 进程记录。"""

    计划: ROS启动计划
    进程: asyncio.subprocess.Process
    日志文件: Path
    日志句柄: BinaryIO
    启动时间: datetime
    监控任务: asyncio.Task[None]
    预期停止: bool = False
    扩展信息: dict[str, Any] = field(default_factory=dict)

    def 导出摘要(self) -> ROS进程摘要:
        """导出摘要。"""
        return ROS进程摘要(
            名称=self.计划.名称,
            包名=self.计划.包名,
            启动文件=self.计划.启动文件,
            pid=self.进程.pid,
            命令=self.计划.命令,
            工作目录=self.计划.工作空间目录,
            日志文件=str(self.日志文件),
            启动时间=self.启动时间.isoformat(),
            运行中=self.进程.returncode is None,
        )


class ROS进程管理服务:
    """负责启动、停止并监控 ROS2 launch 进程。"""

    def __init__(self, 工作空间服务: ROS工作空间服务, 日志目录: Path) -> None:
        self._工作空间服务 = 工作空间服务
        self._日志目录 = 日志目录
        self._进程记录: dict[str, ROS进程记录] = {}
        self._退出回调: 退出回调类型 | None = None

    def 设置退出回调(self, callback: 退出回调类型) -> None:
        """注册进程退出回调。"""
        self._退出回调 = callback

    def 是否运行(self, 名称: str) -> bool:
        """检查指定计划是否正在运行。"""
        record = self._进程记录.get(名称)
        return record is not None and record.进程.returncode is None

    def 获取运行中进程摘要(self) -> dict[str, dict[str, Any]]:
        """返回当前运行中的 ROS 进程摘要。"""
        return {
            name: record.导出摘要().导出字典()
            for name, record in self._进程记录.items()
            if record.进程.returncode is None
        }

    async def 启动(self, 名称: str, 额外参数: dict[str, str] | None = None) -> dict[str, Any]:
        """启动指定 ROS 计划。"""
        self._校验运行环境()
        self._校验工作空间就绪()

        existing = self._进程记录.get(名称)
        if existing is not None and existing.进程.returncode is None:
            return existing.导出摘要().导出字典()

        try:
            计划 = self._工作空间服务.获取启动计划项(名称, 额外参数=额外参数)
        except KeyError as exc:
            raise ROS进程服务错误("ros_plan_not_found", str(exc)) from exc

        self._日志目录.mkdir(parents=True, exist_ok=True)
        日志文件 = self._日志目录 / f"{名称}.log"
        日志句柄 = 日志文件.open("ab")
        try:
            进程 = await asyncio.create_subprocess_shell(
                计划.命令,
                cwd=计划.工作空间目录,
                stdout=日志句柄,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as exc:
            日志句柄.close()
            raise ROS进程服务错误("ros_process_start_failed", f"启动 ROS 进程失败: {名称}, {exc}") from exc

        记录 = ROS进程记录(
            计划=计划,
            进程=进程,
            日志文件=日志文件,
            日志句柄=日志句柄,
            启动时间=datetime.now(),
            监控任务=asyncio.create_task(asyncio.sleep(0)),
        )
        记录.监控任务 = asyncio.create_task(self._监控进程(名称, 记录))
        self._进程记录[名称] = 记录

        logger.info("ROS 进程已启动: name=%s pid=%s log=%s", 名称, 进程.pid, 日志文件)
        await asyncio.sleep(0.3)
        if 进程.returncode is not None:
            raise ROS进程服务错误(
                "ros_process_exited_early",
                f"ROS 进程启动后立即退出: {名称}, exit_code={进程.returncode}",
            )
        return 记录.导出摘要().导出字典()

    async def 停止(self, 名称: str, timeout_sec: float = 10.0) -> dict[str, Any]:
        """停止指定 ROS 计划。"""
        record = self._进程记录.get(名称)
        if record is None or record.进程.returncode is not None:
            return {
                "name": 名称,
                "running": False,
                "stopped": False,
            }

        record.预期停止 = True
        logger.info("准备停止 ROS 进程: name=%s pid=%s", 名称, record.进程.pid)

        if record.进程.returncode is None:
            self._结束进程组(record, int(signal.SIGTERM))

        try:
            await asyncio.wait_for(record.进程.wait(), timeout=timeout_sec)
        except TimeoutError:
            logger.warning("ROS 进程超时未退出，准备强制杀死: name=%s pid=%s", 名称, record.进程.pid)
            self._结束进程组(record, int(getattr(signal, "SIGKILL", signal.SIGTERM)))
            await asyncio.wait_for(record.进程.wait(), timeout=5.0)

        await record.监控任务
        return {
            "name": 名称,
            "running": False,
            "stopped": True,
            "exit_code": record.进程.returncode,
            "log_file": str(record.日志文件),
        }

    async def 关闭(self) -> None:
        """关闭所有 ROS 进程。"""
        for 名称 in ("navigation", "localization", "mapping", "bringup"):
            await self.停止(名称)

    async def _监控进程(self, 名称: str, record: ROS进程记录) -> None:
        """等待进程退出并触发清理。"""
        exit_code = await record.进程.wait()
        self._进程记录.pop(名称, None)

        try:
            record.日志句柄.flush()
        finally:
            record.日志句柄.close()

        if record.预期停止:
            logger.info("ROS 进程已退出: name=%s pid=%s exit_code=%s", 名称, record.进程.pid, exit_code)
        else:
            logger.warning("ROS 进程异常退出: name=%s pid=%s exit_code=%s", 名称, record.进程.pid, exit_code)

        if self._退出回调 is None:
            return

        maybe_result = self._退出回调(名称, exit_code, record.预期停止)
        if inspect.isawaitable(maybe_result):
            await maybe_result

    def _结束进程组(self, record: ROS进程记录, sig: int) -> None:
        """优先结束整个进程组，避免 ros2 launch 子进程残留。"""
        if record.进程.returncode is not None or record.进程.pid is None:
            return

        killpg = getattr(os, "killpg", None)
        try:
            if callable(killpg):
                killpg(record.进程.pid, sig)
                return
            raise OSError("killpg unavailable")
        except ProcessLookupError:
            return
        except OSError:
            if sig == int(signal.SIGTERM):
                record.进程.terminate()
            else:
                record.进程.kill()

    def _校验运行环境(self) -> None:
        if os.name != "posix":
            raise ROS进程服务错误(
                "ros_platform_unsupported",
                "ROS2 进程编排当前只支持 Linux/WSL 运行。",
            )

    def _校验工作空间就绪(self) -> None:
        summary = self._工作空间服务.获取工作空间摘要()
        if not summary["workspace_exists"]:
            raise ROS进程服务错误("ros_workspace_missing", "缺少 robot-ros 工作空间目录。")
        if not summary["install_setup_ready"]:
            raise ROS进程服务错误(
                "ros_workspace_not_built",
                "缺少 robot-ros/install/setup.bash，请先执行 colcon build --symlink-install。",
            )


__all__ = [
    "ROS进程摘要",
    "ROS进程服务错误",
    "ROS进程管理服务",
]
