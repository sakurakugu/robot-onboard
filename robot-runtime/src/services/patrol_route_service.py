from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class 巡逻点:
    """单个巡逻点位。"""

    名称: str
    x: float
    y: float
    yaw: float
    坐标系: str = "map"
    地图名称: str | None = None
    到点等待秒数: float | None = None

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "name": self.名称,
            "x": self.x,
            "y": self.y,
            "yaw": self.yaw,
            "frame_id": self.坐标系,
            "map_name": self.地图名称,
            "arrival_wait_sec": self.到点等待秒数,
        }


@dataclass(frozen=True)
class 巡逻路线:
    """巡逻路线定义。"""

    名称: str
    文件路径: str
    地图名称: str | None
    循环执行: bool
    默认到点等待秒数: float
    路点列表: list[巡逻点]

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "name": self.名称,
            "file": self.文件路径,
            "map_name": self.地图名称,
            "loop": self.循环执行,
            "arrival_wait_sec": self.默认到点等待秒数,
            "waypoint_count": len(self.路点列表),
            "waypoints": [waypoint.导出字典() for waypoint in self.路点列表],
        }


class 巡逻路线加载错误(RuntimeError):
    """巡逻路线加载错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class 巡逻路线服务:
    """负责解析巡逻路线文件。"""

    def 加载路线(self, route_file: Path, 默认任务名称: str | None = None) -> 巡逻路线:
        """从 JSON 文件加载巡逻路线。"""
        try:
            payload = json.loads(route_file.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise 巡逻路线加载错误("waypoint_file_not_found", f"路点文件不存在: {route_file}") from exc
        except json.JSONDecodeError as exc:
            raise 巡逻路线加载错误("waypoint_file_invalid_json", f"路点文件不是合法 JSON: {exc}") from exc

        if isinstance(payload, dict):
            route_name = self._读取可选字符串(payload, "name") or (默认任务名称 or route_file.stem)
            route_map = self._读取可选字符串(payload, "map_name", "mapName")
            loop = self._读取布尔值(payload, "loop", fallback=False)
            arrival_wait_sec = self._读取浮点值(payload, "arrival_wait_sec", "arrivalWaitSec", fallback=0.0)
            raw_waypoints = payload.get("waypoints")
        elif isinstance(payload, list):
            route_name = 默认任务名称 or route_file.stem
            route_map = None
            loop = False
            arrival_wait_sec = 0.0
            raw_waypoints = payload
        else:
            raise 巡逻路线加载错误("waypoint_file_invalid_root", "路点文件根节点必须是对象或数组")

        if not isinstance(raw_waypoints, list):
            raise 巡逻路线加载错误("waypoint_list_missing", "路点文件缺少 waypoints 数组")
        if not raw_waypoints:
            raise 巡逻路线加载错误("waypoint_list_empty", "路点列表不能为空")

        waypoints: list[巡逻点] = []
        for index, item in enumerate(raw_waypoints, start=1):
            if not isinstance(item, dict):
                raise 巡逻路线加载错误("waypoint_item_invalid", f"第 {index} 个路点必须是对象")

            try:
                waypoint = 巡逻点(
                    名称=self._读取可选字符串(item, "name") or f"wp-{index}",
                    x=self._读取必填浮点值(item, "x"),
                    y=self._读取必填浮点值(item, "y"),
                    yaw=self._读取必填浮点值(item, "yaw"),
                    坐标系=self._读取可选字符串(item, "frame_id", "frameId") or "map",
                    地图名称=self._读取可选字符串(item, "map_name", "mapName") or route_map,
                    到点等待秒数=self._读取可选浮点值(item, "arrival_wait_sec", "arrivalWaitSec", "wait_sec", "waitSec"),
                )
            except ValueError as exc:
                raise 巡逻路线加载错误("waypoint_item_invalid", f"第 {index} 个路点格式错误: {exc}") from exc
            waypoints.append(waypoint)

        self._校验地图一致性(route_map, waypoints)
        return 巡逻路线(
            名称=route_name,
            文件路径=str(route_file),
            地图名称=route_map,
            循环执行=loop,
            默认到点等待秒数=arrival_wait_sec,
            路点列表=waypoints,
        )

    def _校验地图一致性(self, route_map: str | None, waypoints: list[巡逻点]) -> None:
        """当前阶段仅支持单地图巡逻。"""
        map_names = {name for name in ([route_map] + [waypoint.地图名称 for waypoint in waypoints]) if name}
        if len(map_names) > 1:
            raise 巡逻路线加载错误("waypoint_multi_map_unsupported", f"当前巡逻执行器仅支持单地图路线，检测到: {sorted(map_names)}")

    def _读取可选字符串(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _读取必填浮点值(self, payload: dict[str, Any], key: str) -> float:
        value = payload.get(key)
        if value is None:
            raise ValueError(f"缺少必要字段: {key}")
        return float(value)

    def _读取浮点值(self, payload: dict[str, Any], *keys: str, fallback: float) -> float:
        value = self._读取可选浮点值(payload, *keys)
        if value is None:
            return fallback
        return value

    def _读取可选浮点值(self, payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if value is None or value == "":
                continue
            return float(value)
        return None

    def _读取布尔值(self, payload: dict[str, Any], key: str, fallback: bool) -> bool:
        if key not in payload:
            return fallback
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        return bool(value)


__all__ = [
    "巡逻点",
    "巡逻路线",
    "巡逻路线加载错误",
    "巡逻路线服务",
]
