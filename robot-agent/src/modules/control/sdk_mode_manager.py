from typing import Awaitable, Callable

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")


class SDK模式管理器:
    """负责切换 SDK 模式与遥控模式。"""

    def __init__(
        self,
        获取SDK模式启用状态: Callable[[], bool],
        设置SDK模式启用状态: Callable[[bool], None],
        执行关闭前动作: Callable[[str], Awaitable[None]],
    ) -> None:
        self._获取SDK模式启用状态 = 获取SDK模式启用状态
        self._设置SDK模式启用状态 = 设置SDK模式启用状态
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
                前缀 = f"{日志前缀} " if 日志前缀 else ""
                logger.info(f"{前缀}当前版本已改为由 robot-runtime + dog_bridge 统一执行动作，跳过本地 SDK 子进程启动")
                self._设置SDK模式启用状态(True)
                return (True, True, None)

            try:
                await self._执行关闭前动作(日志前缀)
            except Exception as e:
                前缀 = f"{日志前缀} " if 日志前缀 else ""
                logger.warning(f"{前缀}关闭 SDK 前执行退出动作失败: {e}")

            self._设置SDK模式启用状态(False)
            return (True, False, None)
        except Exception as e:
            return (False, self._获取SDK模式启用状态(), str(e))
