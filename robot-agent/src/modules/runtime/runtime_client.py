from typing import Any, AsyncIterator

from sparkrobot_common import 格式化运行时IPC异常, 运行时IPC客户端, get_logger

logger = get_logger("robot-agent")


class 本地运行时客户端:
    """封装 robot-runtime 的本地 IPC 调用。"""

    def __init__(self, timeout_sec: float = 5.0) -> None:
        self.timeout_sec = timeout_sec

    def 创建客户端(self) -> 运行时IPC客户端:
        """创建底层 IPC 客户端。"""
        return 运行时IPC客户端(timeout_sec=self.timeout_sec)

    def 格式化异常(self, exc: Exception) -> dict[str, Any]:
        """格式化异常信息。"""
        if isinstance(exc, ValueError):
            return {
                "code": "invalid_command",
                "message": str(exc),
                "details": {},
            }
        return 格式化运行时IPC异常(exc)

    async def 获取状态摘要(self) -> dict[str, Any]:
        """获取运行时状态摘要。"""
        return await self.创建客户端().获取摘要()

    async def 订阅状态摘要(self, interval_sec: float = 1.0) -> AsyncIterator[dict[str, Any]]:
        """订阅运行时摘要状态。"""
        client = self.创建客户端()
        async for event in client.订阅状态(mode="summary", interval_sec=interval_sec):
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                yield payload

    async def 获取激光扫描(self) -> dict[str, Any]:
        """获取最近一帧激光扫描。"""
        return await self.创建客户端().调用("lidar.get_scan")

    async def 获取地图预览(self) -> dict[str, Any]:
        """获取最近一帧建图地图预览。"""
        return await self.创建客户端().获取地图预览()

    async def 执行导航命令(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行导航命令。"""
        client = self.创建客户端()
        command = self._提取命令(data, 默认命令="navigate_to")

        if command in {"navigate_to", "go_to", "start"}:
            goal = self._提取目标(data)
            return await client.导航到目标(
                x=self._读取浮点(goal, "x"),
                y=self._读取浮点(goal, "y"),
                yaw=self._读取浮点(goal, "yaw"),
                frame_id=self._读取字符串(goal, "frame_id", "frameId", 默认值="map"),
                map_name=self._读取可选字符串(goal, "map_name", "mapName"),
                goal_id=self._读取可选字符串(goal, "goal_id", "goalId"),
            )

        if command in {"cancel", "stop"}:
            return await client.取消导航()

        if command == "pause":
            return await client.暂停任务()

        if command in {"resume", "continue"}:
            return await client.恢复任务()

        if command in {"terminate", "abort"}:
            return await client.终止任务()

        raise ValueError(f"不支持的导航命令: {command}")

    async def 执行地图命令(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行建图与定位相关命令。"""
        client = self.创建客户端()
        command = self._提取命令(data, 默认命令="start")

        if command in {"start", "start_mapping", "mapping.start"}:
            return await client.开始建图(self._读取可选字符串(data, "map_name", "mapName", "name"))

        if command in {"stop", "stop_mapping", "mapping.stop"}:
            save_map = self._读取可选布尔值(data, "save_map", "saveMap")
            return await client.停止建图(save_map)

        if command in {"save", "save_map"}:
            return await client.停止建图(True)

        if command in {"load", "load_map", "mapping.load"}:
            map_name = self._读取字符串(data, "map_name", "mapName", "name")
            return await client.加载地图(map_name)

        if command in {"start_localization", "localization.start"}:
            return await client.开始定位(self._读取可选字符串(data, "map_name", "mapName", "name"))

        if command in {"stop_localization", "localization.stop"}:
            return await client.停止定位()

        if command in {"set_initial_pose", "localization.set_initial_pose"}:
            pose = self._提取目标(data)
            return await client.设置初始位姿(
                x=self._读取浮点(pose, "x"),
                y=self._读取浮点(pose, "y"),
                yaw=self._读取浮点(pose, "yaw"),
                frame_id=self._读取字符串(pose, "frame_id", "frameId", 默认值="map"),
                map_name=self._读取可选字符串(pose, "map_name", "mapName"),
            )

        raise ValueError(f"不支持的地图命令: {command}")

    async def 执行巡逻命令(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行巡逻命令。"""
        client = self.创建客户端()
        command = self._提取命令(data, 默认命令="start")

        if command in {"start", "patrol.start"}:
            waypoint_file = self._读取字符串(data, "waypoint_file", "waypointFile", "file")
            task_name = self._读取可选字符串(data, "task_name", "taskName", "name")
            if task_name is None:
                task_name = waypoint_file
            return await client.开始巡逻(task_name, waypoint_file)

        if command == "pause":
            return await client.暂停任务()

        if command in {"resume", "continue"}:
            return await client.恢复任务()

        if command in {"terminate", "stop", "abort"}:
            return await client.终止任务()

        raise ValueError(f"不支持的巡逻命令: {command}")

    def _提取命令(self, data: dict[str, Any], 默认命令: str) -> str:
        command = self._读取可选字符串(data, "command", "action", "operation", "op")
        return (command or 默认命令).strip().lower()

    def _提取目标(self, data: dict[str, Any]) -> dict[str, Any]:
        goal = data.get("goal")
        if isinstance(goal, dict):
            return goal
        pose = data.get("pose")
        if isinstance(pose, dict):
            return pose
        return data

    def _读取字符串(self, data: dict[str, Any], *keys: str, 默认值: str | None = None) -> str:
        value = self._读取可选字符串(data, *keys)
        if value is None:
            if 默认值 is not None:
                return 默认值
            raise ValueError(f"缺少必要参数: {'/'.join(keys)}")
        return value

    def _读取可选字符串(self, data: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _读取浮点(self, data: dict[str, Any], key: str) -> float:
        value = data.get(key)
        if value is None:
            raise ValueError(f"缺少必要参数: {key}")
        return float(value)

    def _读取可选布尔值(self, data: dict[str, Any], *keys: str) -> bool | None:
        for key in keys:
            if key in data:
                value = data.get(key)
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    text = value.strip().lower()
                    if text in {"true", "1", "yes", "on"}:
                        return True
                    if text in {"false", "0", "no", "off"}:
                        return False
                return bool(value)
        return None
