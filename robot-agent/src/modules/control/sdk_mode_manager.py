from pathlib import Path
from typing import Any, Awaitable, Callable

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")


class SDK模式管理器:
    """负责切换 SDK 模式与遥控模式。"""

    def __init__(
        self,
        交互式子进程控制器: Any,
        动作调度器: Any,
        获取SDK模式启用状态: Callable[[], bool],
        设置SDK模式启用状态: Callable[[bool], None],
        创建动作控制器: Callable[[], Any],
        设置动作控制器: Callable[[Any | None], None],
        获取执行器脚本路径: Callable[[], Path],
        执行关闭前动作: Callable[[str], Awaitable[None]],
    ) -> None:
        self.交互式子进程控制器 = 交互式子进程控制器
        self.动作调度器 = 动作调度器
        self._获取SDK模式启用状态 = 获取SDK模式启用状态
        self._设置SDK模式启用状态 = 设置SDK模式启用状态
        self._创建动作控制器 = 创建动作控制器
        self._设置动作控制器 = 设置动作控制器
        self._获取执行器脚本路径 = 获取执行器脚本路径
        self._执行关闭前动作 = 执行关闭前动作

    def 当前是否启用(self) -> bool:
        """返回当前是否启用 SDK 模式。"""
        return self._获取SDK模式启用状态()

    async def 切换(self, enabled: bool, 日志前缀: str = "") -> tuple[bool, bool, str | None]:
        """切换 SDK 模式，返回(是否成功, 当前模式, 错误信息)。"""
        当前模式 = self._获取SDK模式启用状态()
        if 当前模式 == enabled:
            return (True, 当前模式, None)

        try:
            if enabled:
                script_path = self._获取执行器脚本路径()
                if not script_path.exists():
                    return (False, 当前模式, f"找不到交互式脚本: {script_path}")
                if not self.交互式子进程控制器.启动(str(script_path)):
                    return (False, 当前模式, "无法启动交互式子进程")

                self._设置动作控制器(self._创建动作控制器())
                self._设置SDK模式启用状态(True)
                return (True, True, None)

            self.动作调度器.清空并中断()
            try:
                await self._执行关闭前动作(日志前缀)
            except Exception as e:
                前缀 = f"{日志前缀} " if 日志前缀 else ""
                logger.warning(f"{前缀}关闭 SDK 前执行退出动作失败: {e}")

            self.交互式子进程控制器.关闭()
            self._设置动作控制器(None)
            self._设置SDK模式启用状态(False)
            return (True, False, None)
        except Exception as e:
            return (False, self._获取SDK模式启用状态(), str(e))
