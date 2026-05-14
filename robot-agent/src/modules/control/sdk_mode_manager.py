from typing import Any, Awaitable, Callable

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")


class SDK模式管理器:
    """负责切换 SDK 模式与遥控模式。"""

    def __init__(
        self,
        获取SDK模式启用状态: Callable[[], bool],
        设置SDK模式启用状态: Callable[[bool], None],
        执行SDK模式切换: Callable[[bool, str], Awaitable[dict[str, Any]]],
    ) -> None:
        self._获取SDK模式启用状态 = 获取SDK模式启用状态
        self._设置SDK模式启用状态 = 设置SDK模式启用状态
        self._执行SDK模式切换 = 执行SDK模式切换

    def 当前是否启用(self) -> bool:
        """返回当前是否启用 SDK 模式。"""
        return self._获取SDK模式启用状态()

    async def 切换(self, enabled: bool, 日志前缀: str = "") -> tuple[bool, bool, str | None]:
        """切换 SDK 模式，返回(是否成功, 当前模式, 错误信息)。"""
        当前模式 = self._获取SDK模式启用状态()
        if 当前模式 == enabled:
            return (True, 当前模式, None)

        try:
            result = await self._执行SDK模式切换(enabled, 日志前缀)
            payload = result.get("data", {})
            if not isinstance(payload, dict):
                payload = {}

            当前模式 = bool(payload.get("sdk_mode", enabled))
            self._设置SDK模式启用状态(当前模式)
            return (True, 当前模式, None)
        except Exception as e:
            return (False, self._获取SDK模式启用状态(), str(e))
