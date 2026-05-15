from __future__ import annotations

import asyncio
import math
import shlex
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from sparkrobot_common import WORKSPACE_DIR, get_logger

from src.core.state import 任务状态, 动作控制状态, 导航状态, 手动控制状态, 机器人状态存储

from .agent_ipc_service import 机器人代理IPC客户端
from .patrol_route_service import 巡逻路线, 巡逻路线加载错误, 巡逻路线服务
from .robot_telemetry_service import 机器狗遥测服务, 机器狗遥测错误
from .ros_nav_bridge_service import ROS导航桥客户端, ROS导航桥错误
from .ros_process_service import ROS进程服务错误, ROS进程管理服务
from .ros_workspace_service import ROS工作空间服务

logger = get_logger("robot-runtime")


@dataclass(frozen=True)
class 导航目标:
    """运行时侧导航目标。"""

    x: float
    y: float
    yaw: float
    frame_id: str = "map"
    地图名称: str | None = None
    目标ID: str | None = None

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "id": self.目标ID,
            "map_name": self.地图名称,
            "frame_id": self.frame_id,
            "x": self.x,
            "y": self.y,
            "yaw": self.yaw,
        }


@dataclass(frozen=True)
class 初始位姿目标:
    """运行时侧定位初始位姿。"""

    x: float
    y: float
    yaw: float
    frame_id: str = "map"
    地图名称: str | None = None

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "map_name": self.地图名称,
            "frame_id": self.frame_id,
            "x": self.x,
            "y": self.y,
            "yaw": self.yaw,
        }


@dataclass(frozen=True)
class 命令执行结果:
    """统一控制命令执行结果。"""

    成功: bool
    消息: str
    错误码: str | None = None
    数据: dict[str, Any] = field(default_factory=dict)

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "success": self.成功,
            "message": self.消息,
            "error_code": self.错误码,
            "data": self.数据,
        }

    @classmethod
    def 成功结果(cls, message: str, data: dict[str, Any] | None = None) -> "命令执行结果":
        """构造成功结果。"""
        return cls(True, message, None, data or {})

    @classmethod
    def 失败结果(cls, error_code: str, message: str, data: dict[str, Any] | None = None) -> "命令执行结果":
        """构造失败结果。"""
        return cls(False, message, error_code, data or {})


@dataclass
class 导航任务上下文:
    """单点导航上下文。"""

    任务ID: str
    目标: 导航目标
    已暂停: bool = False


@dataclass
class 巡逻上下文:
    """巡逻执行上下文。"""

    任务ID: str
    路线: 巡逻路线
    当前路点索引: int = 0
    已完成圈数: int = 0
    等待截止时间: float | None = None
    上次桥接状态: str | None = None
    当前目标ID: str | None = None
    已暂停: bool = False


@dataclass(frozen=True)
class 手动控制指令:
    """运行时侧手动控制指令。"""

    会话ID: str
    模式: str
    来源: str
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0

    def 导出字典(self) -> dict[str, Any]:
        return {
            "session_id": self.会话ID,
            "mode": self.模式,
            "source": self.来源,
            "velocity": {
                "vx": self.vx,
                "vy": self.vy,
                "wz": self.wz,
            },
        }


@dataclass(frozen=True)
class 动作执行请求:
    """运行时侧动作执行请求。"""

    动作名称: str
    来源: str
    参数: dict[str, Any] = field(default_factory=dict)
    动作ID: str | None = None

    def 导出字典(self) -> dict[str, Any]:
        return {
            "action_id": self.动作ID,
            "name": self.动作名称,
            "source": self.来源,
            "parameters": self.参数,
        }


class 运行时控制服务:
    """运行时控制服务。"""

    def __init__(
        self,
        状态存储: 机器人状态存储,
        config: dict[str, Any],
        ros工作空间服务: ROS工作空间服务,
        ros进程服务: ROS进程管理服务,
        ros导航桥客户端: ROS导航桥客户端,
        机器人代理客户端: 机器人代理IPC客户端,
    ) -> None:
        self.状态存储 = 状态存储
        self.config = config
        self.ros工作空间服务 = ros工作空间服务
        self.ros进程服务 = ros进程服务
        self.ros导航桥客户端 = ros导航桥客户端
        self.机器人代理客户端 = 机器人代理客户端
        self.巡逻路线服务 = 巡逻路线服务()
        self.机器狗遥测服务 = 机器狗遥测服务()

        self.map_dir = self._解析目录配置("mapping", "map_save_dir", WORKSPACE_DIR / "maps")
        self.waypoint_dir = self._解析目录配置("patrol", "waypoint_dir", WORKSPACE_DIR / "waypoints")
        self.默认地图配置 = self._读取可选字符串("localization", "default_map")
        self.建图自动保存 = self._读取布尔值("mapping", "auto_save_on_stop", True)
        self.导航请求超时秒数 = self._读取浮点值("navigation", "goal_timeout_sec", 120.0)
        self.导航桥Action就绪等待秒数 = self._读取浮点值("navigation", "action_ready_timeout_sec", 30.0)
        self.导航桥Action轮询秒数 = self._读取浮点值("navigation", "action_ready_poll_interval_sec", 0.5)
        self.巡逻默认等待秒数 = self._读取浮点值("patrol", "arrival_wait_sec", 2.0)
        self.巡逻默认循环 = self._读取布尔值("patrol", "loop", False)

        self._导航上下文: 导航任务上下文 | None = None
        self._巡逻上下文: 巡逻上下文 | None = None
        self._上次机器狗遥测错误时间 = 0.0
        self._上次bringup自启动时间 = 0.0
        self._手动控制会话: 手动控制指令 | None = None
        self._当前动作请求: 动作执行请求 | None = None

    def _解析目录配置(self, section: str, key: str, fallback: Path) -> Path:
        """解析目录配置。"""
        configured = self._读取可选字符串(section, key)
        if not configured:
            return fallback
        return Path(configured).expanduser()

    def _读取配置分组(self, section: str) -> dict[str, Any]:
        value = self.config.get(section, {})
        if isinstance(value, dict):
            return value
        return {}

    def _读取可选字符串(self, section: str, key: str) -> str | None:
        value = self._读取配置分组(section).get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _读取布尔值(self, section: str, key: str, fallback: bool) -> bool:
        value = self._读取配置分组(section).get(key)
        if value is None:
            return fallback
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        return bool(value)

    def _读取浮点值(self, section: str, key: str, fallback: float) -> float:
        value = self._读取配置分组(section).get(key)
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _获取快照(self) -> Any:
        return self.状态存储.获取快照()

    def _更新建图状态(
        self,
        state: str,
        当前地图: str | None = None,
        最近地图: str | None = None,
    ) -> None:
        snapshot = self._获取快照()
        mapping = snapshot.建图
        mapping.状态 = state
        if 当前地图 is not None:
            mapping.当前地图 = 当前地图
        if 最近地图 is not None:
            mapping.最近地图 = 最近地图
        self.状态存储.更新建图状态(mapping)

    def _更新定位状态(
        self,
        state: str,
        地图名称: str | None = None,
        置信度: float | None = None,
    ) -> None:
        snapshot = self._获取快照()
        localization = snapshot.定位
        localization.状态 = state
        if 地图名称 is not None:
            localization.地图名称 = 地图名称
        localization.置信度 = 置信度
        self.状态存储.更新定位状态(localization)

    def _更新导航状态(
        self,
        state: str,
        当前目标: dict[str, Any] | None,
        剩余距离: float | None,
        失败原因: str | None,
    ) -> None:
        navigation = 导航状态(
            状态=state,
            当前目标=当前目标,
            剩余距离=剩余距离,
            失败原因=失败原因,
        )
        self.状态存储.更新导航状态(navigation)

    def _更新任务状态(self, state: str, task_type: str | None, task_id: str | None) -> None:
        self.状态存储.更新任务状态(
            任务状态(
                状态=state,
                任务类型=task_type,
                任务ID=task_id,
            )
        )

    def _更新控制域状态(
        self,
        当前控制源: str | None = None,
        当前控制模式: str | None = None,
        急停: bool | None = None,
        允许运动: bool | None = None,
        仲裁原因: str | None = None,
    ) -> None:
        snapshot = self._获取快照()
        control = snapshot.控制域
        if 当前控制源 is not None:
            control.当前控制源 = 当前控制源
        if 当前控制模式 is not None:
            control.当前控制模式 = 当前控制模式
        if 急停 is not None:
            control.急停 = 急停
        if 允许运动 is not None:
            control.允许运动 = 允许运动
        if 仲裁原因 is not None:
            control.仲裁原因 = 仲裁原因
        self.状态存储.更新控制域状态(control)

    def _更新手动控制状态(self, state: 手动控制状态) -> None:
        self.状态存储.更新手动控制状态(state)

    def _更新动作控制状态(self, state: 动作控制状态) -> None:
        self.状态存储.更新动作控制状态(state)

    def _当前时间戳毫秒(self) -> int:
        return int(datetime.now().timestamp() * 1000)

    def _刷新控制域仲裁(self) -> None:
        snapshot = self._获取快照()
        dog_bridge_ready = snapshot.运控桥.在线 and snapshot.运控桥.运动控制启用 and snapshot.运控桥.SDK就绪
        if self._手动控制会话 is not None:
            self._更新控制域状态(
                当前控制源="manual",
                当前控制模式=self._手动控制会话.模式,
                允许运动=dog_bridge_ready,
                仲裁原因="manual_control",
            )
            return
        if self._当前动作请求 is not None:
            self._更新控制域状态(
                当前控制源="action",
                当前控制模式="action",
                允许运动=dog_bridge_ready,
                仲裁原因="action_active",
            )
            return
        if self._巡逻上下文 is not None:
            self._更新控制域状态(
                当前控制源="patrol",
                当前控制模式="navigation",
                允许运动=dog_bridge_ready,
                仲裁原因="patrol_active",
            )
            return
        if self._导航上下文 is not None:
            self._更新控制域状态(
                当前控制源="navigation",
                当前控制模式="navigation",
                允许运动=dog_bridge_ready,
                仲裁原因="navigation_active",
            )
            return
        self._更新控制域状态(
            当前控制源="idle",
            当前控制模式="idle",
            允许运动=False,
            仲裁原因="idle",
        )

    def _更新激光雷达状态(self) -> None:
        snapshot = self._获取快照()
        lidar = snapshot.激光雷达
        bringup_running = self.ros进程服务.是否运行("bringup")
        lidar.已连接 = bool(lidar.启用 and bringup_running)
        lidar.扫描正常 = bool(lidar.启用 and bringup_running)
        self.状态存储.更新激光雷达状态(lidar)

    async def 获取激光扫描(self) -> dict[str, Any]:
        """获取最近一帧激光扫描，并附带当前位姿。"""
        payload = await self.ros导航桥客户端.获取激光扫描()
        payload["pose"] = self._构建当前平面位姿()
        return payload

    async def 获取地图预览(self) -> dict[str, Any]:
        """获取最近一帧建图地图预览。"""
        payload = await self.ros导航桥客户端.获取地图预览()
        snapshot = self._获取快照()
        payload["map_name"] = snapshot.建图.当前地图 or snapshot.建图.最近地图 or ""
        return payload

    async def _同步ROS定位位姿(self) -> bool:
        if not self.ros进程服务.是否运行("localization"):
            return False

        try:
            payload = await self.ros导航桥客户端.获取定位位姿(timeout_sec=1.0)
        except ROS导航桥错误:
            return False

        if payload.get("available") is not True:
            return False

        snapshot = self._获取快照()
        pose = snapshot.位姿
        position = self._解析可选向量(payload.get("position"), 3)
        orientation = self._解析可选向量(payload.get("orientation"), 4)
        confidence = self._解析可选浮点(payload.get("confidence"))
        frame_id = self._解析可选字符串值(payload.get("frame_id"))
        if position is not None:
            pose.x = position[0]
            pose.y = position[1]
        if frame_id:
            pose.坐标系 = frame_id
        if orientation is not None:
            pose.四元数 = list(orientation)
            yaw = self._从四元数解析偏航角(orientation)
            if yaw is not None:
                pose.yaw = yaw
        pose.置信度 = confidence
        self.状态存储.更新位姿状态(pose)

        localization = snapshot.定位
        localization.置信度 = confidence
        self.状态存储.更新定位状态(localization)
        return True

    async def _同步机器狗遥测状态(self) -> None:
        try:
            payload = await asyncio.to_thread(self.机器狗遥测服务.获取完整遥测)
        except 机器狗遥测错误 as exc:
            self._节流记录机器狗遥测错误(exc.message)
            snapshot = self._获取快照()
            health = snapshot.健康
            health.在线 = False
            self.状态存储.更新健康状态(health)
            dog_bridge = snapshot.运控桥
            dog_bridge.在线 = False
            dog_bridge.允许运动 = False
            dog_bridge.遥测在线 = False
            dog_bridge.裁决原因 = "telemetry_unavailable"
            self.状态存储.更新运控桥状态(dog_bridge)
            return

        snapshot = self._获取快照()
        self._应用整机状态(snapshot, payload)
        self._应用反馈状态(snapshot, payload)
        self._应用运控桥状态(snapshot, payload)
        self._应用IMU状态(snapshot, payload)
        self._应用里程与位姿状态(snapshot, payload)

    def _应用整机状态(self, snapshot: Any, payload: dict[str, Any]) -> None:
        dog_state = payload.get("dog_state", {})
        if not isinstance(dog_state, dict):
            dog_state = {}

        health = snapshot.健康
        health.在线 = bool(payload.get("online", False))
        battery = self._解析可选整数(dog_state.get("power"))
        temperature = self._解析可选浮点(dog_state.get("temp"))
        if battery is not None:
            health.电量 = battery
        if temperature is not None:
            health.温度 = temperature
        self.状态存储.更新健康状态(health)

    def _应用反馈状态(self, snapshot: Any, payload: dict[str, Any]) -> None:
        feedback = payload.get("feedback", {})
        if not isinstance(feedback, dict):
            return

        health = snapshot.健康
        control_mode = self._解析可选字符串值(feedback.get("control_mode"))
        motion_mode = self._解析可选字符串值(feedback.get("motion_mode"))
        if control_mode:
            health.控制模式 = control_mode
        if motion_mode:
            health.运动模式 = motion_mode
        self.状态存储.更新健康状态(health)

    def _应用运控桥状态(self, snapshot: Any, payload: dict[str, Any]) -> None:
        bridge_status = payload.get("bridge_status", {})
        dog_bridge = snapshot.运控桥
        if not isinstance(bridge_status, dict):
            dog_bridge.在线 = False
            dog_bridge.允许运动 = False
            dog_bridge.遥测在线 = False
            dog_bridge.裁决原因 = "bridge_status_missing"
            self.状态存储.更新运控桥状态(dog_bridge)
            return

        dog_bridge.在线 = True
        dog_bridge.运动控制启用 = bool(bridge_status.get("motion_control_enabled", False))
        dog_bridge.SDK就绪 = bool(bridge_status.get("sdk_ready", False))
        dog_bridge.遥测在线 = bool(bridge_status.get("telemetry_online", False))
        dog_bridge.允许运动 = bool(bridge_status.get("telemetry_motion_ready", False))
        dog_bridge.急停 = bool(bridge_status.get("emergency_stop", False))
        dog_bridge.裁决原因 = self._解析可选字符串值(bridge_status.get("arbitration_reason")) or "unknown"
        dog_bridge.指令延迟秒 = self._解析可选浮点(bridge_status.get("command_age_sec"))
        dog_bridge.遥测延迟秒 = self._解析可选浮点(bridge_status.get("telemetry_last_success_age_sec"))
        target_velocity = self._解析速度字典(bridge_status.get("target_velocity"))
        output_velocity = self._解析速度字典(bridge_status.get("output_velocity"))
        if target_velocity is not None:
            dog_bridge.目标速度 = target_velocity
        if output_velocity is not None:
            dog_bridge.输出速度 = output_velocity
        self.状态存储.更新运控桥状态(dog_bridge)

    def _应用IMU状态(self, snapshot: Any, payload: dict[str, Any]) -> None:
        imu_info = payload.get("imu_info", {})
        if not isinstance(imu_info, dict):
            return

        imu = snapshot.IMU
        rpy = self._解析可选向量(imu_info.get("rpy"), 3)
        acc = self._解析可选向量(imu_info.get("acc"), 3)
        gyro = self._解析可选向量(imu_info.get("gyro"), 3)
        if rpy is not None:
            imu.欧拉角 = list(rpy)
        if acc is not None:
            imu.加速度 = list(acc)
        if gyro is not None:
            imu.角速度 = list(gyro)
        self.状态存储.更新IMU状态(imu)

    def _应用里程与位姿状态(self, snapshot: Any, payload: dict[str, Any]) -> None:
        odom_info = payload.get("odom_info", {})
        if isinstance(odom_info, dict):
            odom = snapshot.里程
            position = self._解析可选向量(odom_info.get("position"), 3)
            v_body = self._解析可选向量(odom_info.get("v_body"), 3)
            omega_body = self._解析可选向量(odom_info.get("omega_body"), 3)
            if position is not None:
                odom.x = position[0]
                odom.y = position[1]
            if v_body is not None:
                odom.vx = v_body[0]
                odom.vy = v_body[1]
            if omega_body is not None:
                odom.偏航角速度 = omega_body[2]
            self.状态存储.更新里程状态(odom)

        navigation_state = payload.get("navigation_state", {})
        if not isinstance(navigation_state, dict):
            return
        current_pose = navigation_state.get("current_pose", {})
        if not isinstance(current_pose, dict):
            return

        pose = snapshot.位姿
        position = self._解析可选向量(current_pose.get("position"), 3)
        orientation = self._解析可选向量(current_pose.get("orientation"), 4)
        if position is not None:
            pose.x = position[0]
            pose.y = position[1]
        if orientation is not None:
            pose.四元数 = list(orientation)
            yaw = self._从四元数解析偏航角(orientation)
            if yaw is not None:
                pose.yaw = yaw
        self.状态存储.更新位姿状态(pose)

    def _节流记录机器狗遥测错误(self, message: str) -> None:
        current_time = asyncio.get_running_loop().time()
        if current_time - self._上次机器狗遥测错误时间 < 5.0:
            return
        self._上次机器狗遥测错误时间 = current_time
        logger.warning("同步机器狗遥测失败: %s", message)

    async def _确保基础桥接运行(self) -> bool:
        """确保 bringup 常驻，保障运控桥和导航桥 Socket 可用。"""
        if self.ros进程服务.是否运行("bringup"):
            return True

        current_time = asyncio.get_running_loop().time()
        if current_time - self._上次bringup自启动时间 < 5.0:
            return False
        self._上次bringup自启动时间 = current_time

        try:
            bringup_info = await self.ros进程服务.启动("bringup")
        except ROS进程服务错误 as exc:
            logger.warning("自动启动 ROS bringup 失败: %s", exc.message)
            return False

        logger.info("已自动启动 ROS bringup: %s", bringup_info)
        return True

    async def 开始手动控制(
        self,
        模式: str,
        来源: str = "runtime",
        session_id: str | None = None,
    ) -> 命令执行结果:
        """开启或接管手动控制会话。"""
        if self._巡逻上下文 is not None or self._导航上下文 is not None:
            terminate_result = await self.终止当前任务()
            if not terminate_result.成功:
                return terminate_result

        normalized_mode = self._标准化手动控制模式(模式)
        manual_session_id = session_id or str(uuid.uuid4())
        self._手动控制会话 = 手动控制指令(
            会话ID=manual_session_id,
            模式=normalized_mode,
            来源=来源,
            vx=0.0,
            vy=0.0,
            wz=0.0,
        )
        self._更新手动控制状态(
            手动控制状态(
                会话ID=manual_session_id,
                模式=normalized_mode,
                来源=来源,
                激活=True,
                速度={"vx": 0.0, "vy": 0.0, "wz": 0.0},
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._刷新控制域仲裁()
        try:
            control_output = await self.ros导航桥客户端.设置控制速度(
                {
                    "session_id": manual_session_id,
                    "mode": normalized_mode,
                    "source": 来源,
                    "vx": 0.0,
                    "vy": 0.0,
                    "wz": 0.0,
                },
                timeout_sec=1.0,
            )
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})
        return 命令执行结果.成功结果(
            "手动控制已激活",
            {
                "session": self._手动控制会话.导出字典(),
                "control_output": control_output,
            },
        )

    async def 更新手动速度(
        self,
        模式: str,
        vx: float,
        vy: float,
        wz: float,
        来源: str = "runtime",
        session_id: str | None = None,
    ) -> 命令执行结果:
        """更新手动控制速度。"""
        if self._手动控制会话 is None:
            start_result = await self.开始手动控制(模式=模式, 来源=来源, session_id=session_id)
            if not start_result.成功:
                return start_result
        elif session_id and self._手动控制会话.会话ID != session_id:
            return 命令执行结果.失败结果("manual_session_mismatch", "手动控制会话不匹配")

        assert self._手动控制会话 is not None
        normalized_mode = self._标准化手动控制模式(模式)
        self._手动控制会话 = replace(
            self._手动控制会话,
            模式=normalized_mode,
            来源=来源,
            vx=float(vx),
            vy=float(vy),
            wz=float(wz),
        )
        self._更新手动控制状态(
            手动控制状态(
                会话ID=self._手动控制会话.会话ID,
                模式=self._手动控制会话.模式,
                来源=self._手动控制会话.来源,
                激活=True,
                速度={"vx": self._手动控制会话.vx, "vy": self._手动控制会话.vy, "wz": self._手动控制会话.wz},
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._刷新控制域仲裁()
        try:
            control_output = await self.ros导航桥客户端.设置控制速度(
                {
                    "session_id": self._手动控制会话.会话ID,
                    "mode": self._手动控制会话.模式,
                    "source": self._手动控制会话.来源,
                    "vx": self._手动控制会话.vx,
                    "vy": self._手动控制会话.vy,
                    "wz": self._手动控制会话.wz,
                },
                timeout_sec=1.0,
            )
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})
        return 命令执行结果.成功结果(
            "手动速度已更新",
            {
                "session": self._手动控制会话.导出字典(),
                "control_output": control_output,
            },
        )

    async def 停止手动控制(self, session_id: str | None = None) -> 命令执行结果:
        """停止手动控制会话。"""
        if self._手动控制会话 is None:
            return 命令执行结果.成功结果("当前没有活动手动控制会话")
        if session_id and self._手动控制会话.会话ID != session_id:
            return 命令执行结果.失败结果("manual_session_mismatch", "手动控制会话不匹配")

        stopped_session = self._手动控制会话
        self._手动控制会话 = None
        self._更新手动控制状态(
            手动控制状态(
                会话ID=stopped_session.会话ID,
                模式=stopped_session.模式,
                来源=stopped_session.来源,
                激活=False,
                速度={"vx": 0.0, "vy": 0.0, "wz": 0.0},
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._刷新控制域仲裁()
        try:
            control_output = await self.ros导航桥客户端.停止控制(timeout_sec=1.0)
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})
        return 命令执行结果.成功结果(
            "手动控制已停止",
            {"session_id": stopped_session.会话ID, "control_output": control_output},
        )

    async def 执行直连控制(self, payload: dict[str, Any], 来源: str = "runtime") -> 命令执行结果:
        """执行手机直连专用控制命令。"""
        if self._巡逻上下文 is not None or self._导航上下文 is not None:
            terminate_result = await self.终止当前任务()
            if not terminate_result.成功:
                return terminate_result

        control_type = self._解析可选字符串值(payload.get("type")) or "move"
        mode = self._解析可选字符串值(payload.get("mode")) or "move"
        try:
            bridge_output = await self.ros导航桥客户端.执行直连控制(
                {
                    **payload,
                    "type": control_type,
                    "mode": mode,
                    "source": 来源,
                },
                timeout_sec=1.0,
            )
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._更新控制域状态(
            当前控制源="manual",
            当前控制模式=mode,
            急停=False,
            仲裁原因="direct_control",
        )
        return 命令执行结果.成功结果(
            "直连控制已下发",
            {
                "type": control_type,
                "mode": mode,
                "bridge": bridge_output,
            },
        )

    async def 切换SDK模式(self, enabled: bool | None, 来源: str = "runtime") -> 命令执行结果:
        """切换 SDK/遥控模式。"""
        if enabled is None:
            return 命令执行结果.失败结果("invalid_sdk_mode", "enabled 参数不能为空")

        if self._手动控制会话 is not None:
            stop_result = await self.停止手动控制(self._手动控制会话.会话ID)
            if not stop_result.成功:
                return stop_result

        if enabled:
            self._更新控制域状态(
                当前控制源="idle",
                当前控制模式="idle",
                急停=False,
                允许运动=False,
                仲裁原因="sdk_mode_switching",
            )
        else:
            self._更新控制域状态(
                当前控制源="idle",
                当前控制模式="idle",
                急停=False,
                允许运动=False,
                仲裁原因="remote_mode_switching",
            )

        try:
            bridge_output = await self.ros导航桥客户端.切换SDK模式(enabled, timeout_sec=2.0)
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        snapshot = self._获取快照()
        health = snapshot.健康
        health.SDK模式 = enabled
        self.状态存储.更新健康状态(health)

        dog_bridge = snapshot.运控桥
        dog_bridge.运动控制启用 = enabled
        self.状态存储.更新运控桥状态(dog_bridge)
        self._刷新控制域仲裁()
        return 命令执行结果.成功结果(
            "SDK 模式切换成功" if enabled else "已切换为遥控模式",
            {
                "sdk_mode": enabled,
                "source": 来源,
                "bridge": bridge_output,
            },
        )

    async def 立即急停(self, 来源: str = "runtime") -> 命令执行结果:
        """立即触发机器狗急停，不经过普通动作排队。"""
        if self._巡逻上下文 is not None or self._导航上下文 is not None:
            terminate_result = await self.终止当前任务()
            if not terminate_result.成功:
                return terminate_result

        if self._手动控制会话 is not None:
            self._手动控制会话 = None
            self._更新手动控制状态(
                手动控制状态(
                    会话ID=None,
                    模式="move",
                    来源=来源,
                    激活=False,
                    速度={"vx": 0.0, "vy": 0.0, "wz": 0.0},
                    更新时间戳毫秒=self._当前时间戳毫秒(),
                )
            )

        request = 动作执行请求(
            动作名称="estop",
            来源=来源,
            参数={},
            动作ID=str(uuid.uuid4()),
        )
        self._当前动作请求 = request
        self._更新动作控制状态(
            动作控制状态(
                动作名称=request.动作名称,
                状态="running",
                来源=request.来源,
                参数=request.参数,
                动作ID=request.动作ID,
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._更新控制域状态(
            当前控制源="action",
            当前控制模式="action",
            急停=False,
            允许运动=False,
            仲裁原因="estop_requested",
        )
        try:
            bridge_output = await self.ros导航桥客户端.立即急停(
                {
                    "source": 来源,
                    "action_id": request.动作ID,
                },
                timeout_sec=1.0,
            )
        except ROS导航桥错误 as exc:
            self._当前动作请求 = None
            self._更新动作控制状态(
                动作控制状态(
                    动作名称="estop",
                    状态="error",
                    来源=来源,
                    参数={},
                    动作ID=request.动作ID,
                    更新时间戳毫秒=self._当前时间戳毫秒(),
                )
            )
            self._刷新控制域仲裁()
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        return 命令执行结果.成功结果(
            "急停已触发",
            {
                "action": request.导出字典(),
                "bridge": bridge_output,
            },
        )

    async def 执行动作(
        self,
        action_name: str,
        parameters: dict[str, Any] | None = None,
        来源: str = "runtime",
        action_id: str | None = None,
    ) -> 命令执行结果:
        """登记动作执行请求。"""
        normalized_action = str(action_name).strip()
        if not normalized_action:
            return 命令执行结果.失败结果("invalid_action", "动作名称不能为空")
        if self._巡逻上下文 is not None or self._导航上下文 is not None:
            terminate_result = await self.终止当前任务()
            if not terminate_result.成功:
                return terminate_result

        request = 动作执行请求(
            动作名称=normalized_action,
            来源=来源,
            参数=dict(parameters or {}),
            动作ID=action_id or str(uuid.uuid4()),
        )
        self._当前动作请求 = request
        self._更新动作控制状态(
            动作控制状态(
                动作名称=request.动作名称,
                状态="queued",
                来源=request.来源,
                参数=request.参数,
                动作ID=request.动作ID,
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._刷新控制域仲裁()
        try:
            action_output = await self.ros导航桥客户端.执行动作(
                {
                    "action_id": request.动作ID,
                    "action_name": request.动作名称,
                    "source": request.来源,
                    "parameters": request.参数,
                },
                timeout_sec=1.5,
            )
        except ROS导航桥错误 as exc:
            self._当前动作请求 = None
            self._更新动作控制状态(
                动作控制状态(
                    动作名称=request.动作名称,
                    状态="error",
                    来源=request.来源,
                    参数=request.参数,
                    动作ID=request.动作ID,
                    更新时间戳毫秒=self._当前时间戳毫秒(),
                )
            )
            self._刷新控制域仲裁()
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._更新动作控制状态(
            动作控制状态(
                动作名称=request.动作名称,
                状态="running",
                来源=request.来源,
                参数=request.参数,
                动作ID=request.动作ID,
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        return 命令执行结果.成功结果(
            "动作请求已登记",
            {"action": request.导出字典(), "agent": action_output},
        )

    async def 取消动作(self, action_id: str | None = None) -> 命令执行结果:
        """取消当前动作请求。"""
        if self._当前动作请求 is None:
            return 命令执行结果.成功结果("当前没有活动动作请求")
        if action_id and self._当前动作请求.动作ID != action_id:
            return 命令执行结果.失败结果("action_id_mismatch", "动作请求 ID 不匹配")

        current_request = self._当前动作请求
        self._当前动作请求 = None
        self._更新动作控制状态(
            动作控制状态(
                动作名称=current_request.动作名称,
                状态="cancelled",
                来源=current_request.来源,
                参数=current_request.参数,
                动作ID=current_request.动作ID,
                更新时间戳毫秒=self._当前时间戳毫秒(),
            )
        )
        self._刷新控制域仲裁()
        try:
            bridge_output = await self.ros导航桥客户端.取消动作(
                {"action_id": current_request.动作ID},
                timeout_sec=1.0,
            )
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})
        return 命令执行结果.成功结果(
            "动作请求已取消",
            {"action_id": current_request.动作ID, "bridge": bridge_output},
        )

    def _标准化手动控制模式(self, mode: str) -> str:
        normalized = str(mode).strip().lower()
        if normalized not in {"move", "pose", "two_leg"}:
            return "move"
        return normalized

    def _构建当前平面位姿(self) -> dict[str, Any]:
        snapshot = self._获取快照()
        pose = snapshot.位姿
        half_yaw = pose.yaw / 2.0
        return {
            "position": [pose.x, pose.y, 0.0],
            "orientation": [0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw)],
            "yaw": pose.yaw,
            "confidence": pose.置信度,
        }

    def _获取活动任务类型(self) -> str | None:
        if self.ros进程服务.是否运行("mapping"):
            return "mapping"
        if self._巡逻上下文 is not None:
            return "patrol"
        if self._导航上下文 is not None:
            return "navigation"
        return None

    def _生成默认地图名称(self) -> str:
        return f"map-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _解析地图文件(self, map_name: str) -> tuple[str, Path]:
        text = map_name.strip()
        if not text:
            raise ValueError("缺少地图名称")

        candidate = Path(text).expanduser()
        if candidate.is_absolute():
            yaml_path = candidate if candidate.suffix.lower() == ".yaml" else candidate.with_suffix(".yaml")
        else:
            relative = candidate if candidate.suffix.lower() == ".yaml" else candidate.with_suffix(".yaml")
            yaml_path = self.map_dir / relative

        if not yaml_path.exists():
            raise FileNotFoundError(f"地图文件不存在: {yaml_path}")
        return yaml_path.stem, yaml_path

    def _解析定位地图(self, map_name: str | None) -> tuple[str, Path]:
        snapshot = self._获取快照()
        candidate = map_name or snapshot.定位.地图名称 or snapshot.建图.最近地图 or self.默认地图配置
        if not candidate:
            raise ValueError("缺少地图名称，且未配置 localization.default_map")
        return self._解析地图文件(candidate)

    def _解析速度字典(self, value: Any) -> dict[str, float] | None:
        if not isinstance(value, dict):
            return None
        vx = self._解析可选浮点(value.get("vx"))
        vy = self._解析可选浮点(value.get("vy"))
        wz = self._解析可选浮点(value.get("wz"))
        if vx is None or vy is None or wz is None:
            return None
        return {
            "vx": vx,
            "vy": vy,
            "wz": wz,
        }

    def _解析路点文件(self, waypoint_file: str) -> Path:
        candidate = Path(waypoint_file).expanduser()
        if not candidate.suffix:
            candidate = candidate.with_suffix(".json")
        if not candidate.is_absolute():
            candidate = self.waypoint_dir / candidate
        return candidate

    def _标准化导航桥状态(self, state: Any) -> str:
        text = str(state or "idle").strip().lower() or "idle"
        if text == "failed":
            return "error"
        return text

    async def 开始建图(self, map_name: str | None = None) -> 命令执行结果:
        """启动建图流程。"""
        if not self._读取布尔值("mapping", "enabled", False):
            return 命令执行结果.失败结果("mapping_disabled", "当前配置未启用建图能力")

        active_task = self._获取活动任务类型()
        if active_task is not None:
            return 命令执行结果.失败结果("task_busy", f"当前已有任务在执行: {active_task}")

        if self.ros进程服务.是否运行("localization") or self.ros进程服务.是否运行("navigation"):
            return 命令执行结果.失败结果("mapping_conflict", "建图前请先停止定位和导航相关进程")

        resolved_map_name = (map_name or "").strip() or self._生成默认地图名称()
        try:
            bringup_info = await self.ros进程服务.启动("bringup")
            mapping_info = await self.ros进程服务.启动("mapping")
        except ROS进程服务错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message)

        self._导航上下文 = None
        self._巡逻上下文 = None
        self._更新激光雷达状态()
        self._更新建图状态("running", 当前地图=resolved_map_name)
        self._更新定位状态("idle", 地图名称="")
        self._更新导航状态("idle", None, None, None)
        self._更新任务状态("running", "mapping", resolved_map_name)
        return 命令执行结果.成功结果(
            "建图已启动",
            {
                "map_name": resolved_map_name,
                "processes": {
                    "bringup": bringup_info,
                    "mapping": mapping_info,
                },
            },
        )

    async def 停止建图(self, save_map: bool | None = None) -> 命令执行结果:
        """停止建图流程。"""
        snapshot = self._获取快照()
        current_map = snapshot.建图.当前地图
        save_requested = self.建图自动保存 if save_map is None else save_map
        if not self.ros进程服务.是否运行("mapping"):
            self._更新任务状态("idle", None, None)
            self._更新建图状态("idle", 当前地图="")
            return 命令执行结果.成功结果(
                "建图未在运行",
                {
                    "stopped": False,
                    "save_requested": save_requested,
                    "map_name": current_map or None,
                },
            )

        save_result: dict[str, Any] | None = None
        if save_requested and current_map:
            save_result = await self._保存地图(current_map)

        try:
            stop_info = await self.ros进程服务.停止("mapping")
        except ROS进程服务错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message)

        last_map = snapshot.建图.最近地图
        if save_result and save_result.get("saved"):
            last_map = current_map

        self._更新建图状态("idle", 当前地图="", 最近地图=last_map)
        self._更新任务状态("idle", None, None)
        if save_requested and current_map and save_result and not save_result.get("saved"):
            return 命令执行结果.失败结果(
                str(save_result.get("error_code") or "map_save_failed"),
                str(save_result.get("message") or "地图保存失败"),
                {
                    "stopped": True,
                    "stop": stop_info,
                    "save": save_result,
                    "map_name": current_map,
                },
            )
        return 命令执行结果.成功结果(
            "建图已停止",
            {
                "stopped": True,
                "stop": stop_info,
                "save": save_result,
                "map_name": current_map or None,
            },
        )

    async def 加载地图(self, map_name: str) -> 命令执行结果:
        """加载地图元信息。"""
        if self._获取活动任务类型() is not None:
            return 命令执行结果.失败结果("task_busy", "当前存在活动任务，不能切换地图")
        if self.ros进程服务.是否运行("localization") or self.ros进程服务.是否运行("navigation"):
            return 命令执行结果.失败结果("map_in_use", "请先停止定位与导航再加载新地图")
        if self.ros进程服务.是否运行("mapping"):
            return 命令执行结果.失败结果("mapping_active", "建图进行中，不能加载地图")

        try:
            resolved_name, yaml_path = self._解析地图文件(map_name)
        except (FileNotFoundError, ValueError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))

        self._更新建图状态("idle", 当前地图=resolved_name, 最近地图=resolved_name)
        self._更新定位状态("idle", 地图名称=resolved_name)
        return 命令执行结果.成功结果(
            "地图已加载",
            {
                "map_name": resolved_name,
                "map_file": str(yaml_path),
            },
        )

    async def 开始定位(self, map_name: str | None = None) -> 命令执行结果:
        """启动定位流程。"""
        if not self._读取布尔值("localization", "enabled", False):
            return 命令执行结果.失败结果("localization_disabled", "当前配置未启用定位能力")
        if self._获取活动任务类型() is not None:
            return 命令执行结果.失败结果("task_busy", "当前存在活动任务，不能启动定位")
        if self.ros进程服务.是否运行("mapping"):
            return 命令执行结果.失败结果("mapping_active", "建图进行中，不能启动定位")

        try:
            resolved_name, yaml_path = self._解析定位地图(map_name)
            env = await self._确保定位环境就绪(resolved_name, yaml_path)
        except (ValueError, FileNotFoundError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))
        except ROS进程服务错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message)

        return 命令执行结果.成功结果(
            "定位已启动",
            {
                "map_name": resolved_name,
                "map_file": str(yaml_path),
                "processes": env,
            },
        )

    async def 停止定位(self) -> 命令执行结果:
        """停止定位流程。"""
        if self._导航上下文 is not None or self._巡逻上下文 is not None:
            return 命令执行结果.失败结果("task_busy", "当前导航任务执行中，不能停止定位")

        stop_results: dict[str, Any] = {}
        try:
            if self.ros进程服务.是否运行("navigation"):
                stop_results["navigation"] = await self.ros进程服务.停止("navigation")
            if self.ros进程服务.是否运行("localization"):
                stop_results["localization"] = await self.ros进程服务.停止("localization")
        except ROS进程服务错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message)

        snapshot = self._获取快照()
        current_map = snapshot.定位.地图名称
        self._更新定位状态("idle", 地图名称=current_map)
        self._更新导航状态("idle", None, None, None)
        return 命令执行结果.成功结果(
            "定位已停止",
            {
                "stopped": bool(stop_results),
                "processes": stop_results,
                "map_name": current_map or None,
            },
        )

    async def 设置初始位姿(self, x: float, y: float, yaw: float, frame_id: str = "map", 地图名称: str | None = None) -> 命令执行结果:
        """向定位模块发布初始位姿。"""
        if not self._读取布尔值("localization", "enabled", False):
            return 命令执行结果.失败结果("localization_disabled", "当前配置未启用定位能力")

        if not self.ros进程服务.是否运行("localization"):
            return 命令执行结果.失败结果("localization_not_running", "请先启动定位后再设置初始位姿")

        try:
            resolved_map_name, _ = self._解析定位地图(地图名称)
        except (ValueError, FileNotFoundError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))

        pose = 初始位姿目标(
            x=x,
            y=y,
            yaw=yaw,
            frame_id=frame_id,
            地图名称=resolved_map_name,
        )

        try:
            bridge = await self.ros导航桥客户端.设置初始位姿(pose.导出字典())
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        snapshot = self._获取快照()
        runtime_pose = snapshot.位姿
        runtime_pose.坐标系 = pose.frame_id
        runtime_pose.x = pose.x
        runtime_pose.y = pose.y
        runtime_pose.yaw = pose.yaw
        runtime_pose.四元数 = [
            0.0,
            0.0,
            math.sin(pose.yaw / 2.0),
            math.cos(pose.yaw / 2.0),
        ]
        self.状态存储.更新位姿状态(runtime_pose)
        self._更新定位状态("running", 地图名称=resolved_map_name, 置信度=1.0)

        return 命令执行结果.成功结果(
            "初始位姿已设置",
            {
                "pose": pose.导出字典(),
                "bridge": bridge,
            },
        )

    async def 全局重定位(self, 地图名称: str | None = None) -> 命令执行结果:
        """触发一次 AMCL 全局重定位。"""
        if not self._读取布尔值("localization", "enabled", False):
            return 命令执行结果.失败结果("localization_disabled", "当前配置未启用定位能力")

        if not self.ros进程服务.是否运行("localization"):
            return 命令执行结果.失败结果("localization_not_running", "请先启动定位后再执行自动重定位")

        try:
            resolved_map_name, _ = self._解析定位地图(地图名称)
        except (ValueError, FileNotFoundError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))

        try:
            bridge = await self.ros导航桥客户端.全局重定位()
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._更新定位状态("running", 地图名称=resolved_map_name, 置信度=0.0)
        return 命令执行结果.成功结果(
            "已触发自动重定位",
            {
                "map_name": resolved_map_name,
                "bridge": bridge,
            },
        )

    async def 导航到目标(self, goal: 导航目标) -> 命令执行结果:
        """执行单点导航。"""
        if not self._读取布尔值("navigation", "enabled", False):
            return 命令执行结果.失败结果("navigation_disabled", "当前配置未启用导航能力")

        active_task = self._获取活动任务类型()
        if active_task is not None:
            return 命令执行结果.失败结果("task_busy", f"当前已有任务在执行: {active_task}")

        try:
            resolved_map_name, _ = self._解析定位地图(goal.地图名称)
            env = await self._确保导航环境就绪(resolved_map_name)
        except (ValueError, FileNotFoundError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))
        except (ROS进程服务错误, ROS导航桥错误) as exc:
            error_code = getattr(exc, "code", "navigation_prepare_failed")
            return 命令执行结果.失败结果(error_code, str(exc))

        task_id = goal.目标ID or str(uuid.uuid4())
        resolved_goal = 导航目标(
            x=goal.x,
            y=goal.y,
            yaw=goal.yaw,
            frame_id=goal.frame_id,
            地图名称=resolved_map_name,
            目标ID=task_id,
        )
        try:
            bridge = await self._发送导航目标到桥(resolved_goal)
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._导航上下文 = 导航任务上下文(任务ID=task_id, 目标=resolved_goal)
        self._更新任务状态("running", "navigation", task_id)
        self._更新导航状态("pending", resolved_goal.导出字典(), None, None)
        return 命令执行结果.成功结果(
            "导航目标已下发",
            {
                "task_id": task_id,
                "goal": resolved_goal.导出字典(),
                "bridge": bridge,
                "environment": env,
            },
        )

    async def 取消导航(self) -> 命令执行结果:
        """取消单点导航。"""
        if self._巡逻上下文 is not None:
            return 命令执行结果.失败结果("patrol_active", "当前正在执行巡逻，请使用 task.terminate")
        if self._导航上下文 is None:
            return 命令执行结果.失败结果("navigation_not_active", "当前没有活动中的导航任务")

        navigation_ctx = self._导航上下文
        bridge: dict[str, Any] | None = None
        if not navigation_ctx.已暂停:
            try:
                bridge = await self._取消导航桥目标(ignore_goal_missing=True)
            except ROS导航桥错误 as exc:
                return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._导航上下文 = None
        self._更新任务状态("idle", None, None)
        self._更新导航状态("cancelled", navigation_ctx.目标.导出字典(), None, None)
        return 命令执行结果.成功结果(
            "导航已取消",
            {
                "task_id": navigation_ctx.任务ID,
                "bridge": bridge,
            },
        )

    async def _确保定位环境就绪(self, map_name: str, yaml_path: Path) -> dict[str, Any]:
        bringup_info = await self.ros进程服务.启动("bringup")
        current_map = self._获取快照().定位.地图名称
        if current_map != map_name and self.ros进程服务.是否运行("navigation"):
            await self.ros进程服务.停止("navigation")
        if self.ros进程服务.是否运行("localization") and current_map != map_name:
            await self.ros进程服务.停止("localization")
        localization_info = await self.ros进程服务.启动("localization", {"map": str(yaml_path)})

        self._更新激光雷达状态()
        self._更新建图状态("idle", 当前地图=map_name, 最近地图=map_name)
        self._更新定位状态("running", 地图名称=map_name)
        self._更新导航状态("idle", None, None, None)
        return {
            "bringup": bringup_info,
            "localization": localization_info,
        }

    async def _确保导航环境就绪(self, map_name: str) -> dict[str, Any]:
        resolved_name, yaml_path = self._解析定位地图(map_name)
        env = await self._确保定位环境就绪(resolved_name, yaml_path)
        navigation_info = await self.ros进程服务.启动("navigation")
        await self._等待生命周期节点激活("/bt_navigator", timeout_sec=15.0)
        bridge_status = await self.ros导航桥客户端.等待就绪(timeout_sec=10.0)
        bridge_status = await self._等待导航桥Action就绪(bridge_status)
        self._更新导航状态("idle", None, None, None)
        env["navigation"] = navigation_info
        env["bridge"] = bridge_status
        return env

    async def _等待导航桥Action就绪(self, 初始桥状态: dict[str, Any] | None = None) -> dict[str, Any]:
        截止时间 = asyncio.get_running_loop().time() + max(self.导航桥Action就绪等待秒数, 0.0)
        轮询间隔 = max(self.导航桥Action轮询秒数, 0.1)
        最近桥状态 = 初始桥状态 or {}
        最近异常: ROS导航桥错误 | None = None

        while True:
            状态摘要 = 最近桥状态.get("status", {})
            if isinstance(状态摘要, dict) and bool(状态摘要.get("action_server_ready", False)):
                return 最近桥状态

            if not self.ros进程服务.是否运行("navigation"):
                raise ROS导航桥错误("nav_process_not_running", "导航进程未在运行，Nav2 Action 无法就绪", {"status": 状态摘要})

            当前时间 = asyncio.get_running_loop().time()
            if 当前时间 >= 截止时间:
                if 最近异常 is not None:
                    raise ROS导航桥错误(
                        "nav_action_unavailable",
                        f"导航桥已启动，但 Nav2 Action 在 {self.导航桥Action就绪等待秒数:.1f} 秒内仍未就绪: {最近异常.message}",
                        {
                            "status": 状态摘要 if isinstance(状态摘要, dict) else {},
                            "bridge_error_code": 最近异常.code,
                            "bridge_error_details": 最近异常.details,
                        },
                    ) from 最近异常
                raise ROS导航桥错误(
                    "nav_action_unavailable",
                    f"导航桥已启动，但 Nav2 Action 在 {self.导航桥Action就绪等待秒数:.1f} 秒内仍未就绪",
                    {"status": 状态摘要 if isinstance(状态摘要, dict) else {}},
                )

            await asyncio.sleep(min(轮询间隔, max(截止时间 - 当前时间, 0.0)))
            try:
                最近桥状态 = await self.ros导航桥客户端.获取导航状态(timeout_sec=轮询间隔)
                最近异常 = None
            except ROS导航桥错误 as exc:
                最近异常 = exc

    async def _发送导航目标到桥(self, goal: 导航目标) -> dict[str, Any]:
        return await self.ros导航桥客户端.导航到目标(goal.导出字典())

    async def _取消导航桥目标(self, ignore_goal_missing: bool = False) -> dict[str, Any] | None:
        try:
            return await self.ros导航桥客户端.取消导航()
        except ROS导航桥错误 as exc:
            if ignore_goal_missing and exc.code in {"goal_not_active", "goal_cancel_rejected"}:
                return None
            raise

    async def _执行ROS命令(self, command_parts: list[str], timeout_sec: float = 60.0) -> tuple[int, str]:
        if not self.ros工作空间服务.install_setup.exists():
            return 1, "缺少 install/setup.bash，无法执行 ROS 命令"

        ros_command = " ".join(shlex.quote(part) for part in command_parts)
        bash_script = f"source {shlex.quote(str(self.ros工作空间服务.install_setup))} && {ros_command}"
        process = await asyncio.create_subprocess_shell(
            f"bash -lc {shlex.quote(bash_script)}",
            cwd=str(self.ros工作空间服务.workspace_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        except TimeoutError:
            process.kill()
            await process.wait()
            return 124, "命令执行超时"

        output = stdout.decode("utf-8", errors="ignore").strip() if stdout else ""
        return process.returncode or 0, output

    async def _等待生命周期节点激活(self, 节点名: str, timeout_sec: float = 15.0) -> None:
        script = (
            "import sys\n"
            "import time\n"
            "import rclpy\n"
            "from lifecycle_msgs.srv import GetState\n"
            f"node_name = {节点名!r}\n"
            f"timeout_sec = {float(timeout_sec)!r}\n"
            "deadline = time.monotonic() + timeout_sec\n"
            "last_label = ''\n"
            "rclpy.init()\n"
            "node = rclpy.create_node('wait_lifecycle_state_once')\n"
            "client = node.create_client(GetState, f'{node_name}/get_state')\n"
            "try:\n"
            "    while time.monotonic() < deadline:\n"
            "        if not client.wait_for_service(timeout_sec=0.5):\n"
            "            continue\n"
            "        future = client.call_async(GetState.Request())\n"
            "        rclpy.spin_until_future_complete(node, future, timeout_sec=1.0)\n"
            "        result = future.result()\n"
            "        if result is None:\n"
            "            continue\n"
            "        last_label = str(result.current_state.label).strip().lower()\n"
            "        if last_label == 'active':\n"
            "            print(last_label)\n"
            "            sys.exit(0)\n"
            "        time.sleep(0.2)\n"
            "finally:\n"
            "    node.destroy_node()\n"
            "    if rclpy.ok():\n"
            "        rclpy.shutdown()\n"
            "print(last_label or 'timeout')\n"
            "sys.exit(2)\n"
        )
        exit_code, output = await self._执行ROS命令(["python3", "-c", script], timeout_sec=timeout_sec + 5.0)
        if exit_code != 0:
            raise ROS进程服务错误(
                "ros_navigation_not_active",
                f"等待生命周期节点激活超时: node={节点名}, state={output or exit_code}",
            )

    async def _保存地图(self, map_name: str) -> dict[str, Any]:
        map_base = self.map_dir / map_name
        map_base.parent.mkdir(parents=True, exist_ok=True)
        exit_code, output = await self._执行ROS命令(
            ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(map_base)],
            timeout_sec=60.0,
        )
        yaml_file = map_base.with_suffix(".yaml")
        pgm_file = map_base.with_suffix(".pgm")
        saved = exit_code == 0 and yaml_file.exists()
        return {
            "saved": saved,
            "error_code": None if saved else "map_save_failed",
            "message": "地图已保存" if saved else f"地图保存失败: {output or exit_code}",
            "map_base": str(map_base),
            "map_yaml": str(yaml_file),
            "map_image": str(pgm_file),
            "output": output,
        }

    async def 开始巡逻(self, task_name: str, waypoint_file: str) -> 命令执行结果:
        """启动巡逻任务。"""
        if not self._读取布尔值("patrol", "enabled", False):
            return 命令执行结果.失败结果("patrol_disabled", "当前配置未启用巡逻能力")

        active_task = self._获取活动任务类型()
        if active_task is not None:
            return 命令执行结果.失败结果("task_busy", f"当前已有任务在执行: {active_task}")

        route_file = self._解析路点文件(waypoint_file)
        try:
            route = self.巡逻路线服务.加载路线(route_file, 默认任务名称=task_name)
        except 巡逻路线加载错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"waypoint_file": str(route_file)})

        route_map_name = self._解析巡逻地图名称(route)
        if route_map_name is None:
            return 命令执行结果.失败结果("patrol_map_missing", "巡逻路线未指定地图，且当前没有可复用的定位地图")

        try:
            resolved_map_name, _ = self._解析定位地图(route_map_name)
            env = await self._确保导航环境就绪(resolved_map_name)
        except (ValueError, FileNotFoundError) as exc:
            return 命令执行结果.失败结果("map_not_found", str(exc))
        except (ROS进程服务错误, ROS导航桥错误) as exc:
            error_code = getattr(exc, "code", "patrol_prepare_failed")
            return 命令执行结果.失败结果(error_code, str(exc))

        task_id = task_name.strip() or route.名称 or str(uuid.uuid4())
        completed_route = self._补齐巡逻路线地图(route, resolved_map_name)
        self._巡逻上下文 = 巡逻上下文(
            任务ID=task_id,
            路线=completed_route,
        )
        dispatch_result = await self._派发巡逻当前路点()
        if not dispatch_result.成功:
            return dispatch_result

        return 命令执行结果.成功结果(
            "巡逻已启动",
            {
                "task_id": task_id,
                "route": completed_route.导出字典(),
                "environment": env,
                "dispatch": dispatch_result.数据,
            },
        )

    async def 暂停当前任务(self) -> 命令执行结果:
        """暂停当前任务。"""
        if self.ros进程服务.是否运行("mapping"):
            return 命令执行结果.失败结果("mapping_pause_unsupported", "当前版本不支持暂停建图，请使用 task.terminate")
        if self._巡逻上下文 is not None:
            return await self._暂停巡逻任务()
        if self._导航上下文 is not None:
            return await self._暂停导航任务()
        return 命令执行结果.失败结果("task_not_active", "当前没有可暂停的任务")

    async def 恢复当前任务(self) -> 命令执行结果:
        """恢复当前任务。"""
        if self._巡逻上下文 is not None:
            return await self._恢复巡逻任务()
        if self._导航上下文 is not None:
            return await self._恢复导航任务()
        return 命令执行结果.失败结果("task_not_paused", "当前没有可恢复的任务")

    async def 终止当前任务(self) -> 命令执行结果:
        """终止当前任务。"""
        if self.ros进程服务.是否运行("mapping"):
            result = await self.停止建图(False)
            if result.成功:
                return 命令执行结果.成功结果("建图任务已终止", result.数据)
            return result
        if self._巡逻上下文 is not None:
            return await self._终止巡逻任务()
        if self._导航上下文 is not None:
            return await self._终止导航任务()
        return 命令执行结果.失败结果("task_not_active", "当前没有活动任务")

    async def 同步桥接状态(self) -> None:
        """轮询同步导航桥状态。"""
        await self._同步机器狗遥测状态()
        await self._同步ROS定位位姿()
        self._更新激光雷达状态()

        if self._巡逻上下文 is not None and self._巡逻上下文.等待截止时间 is not None and not self._巡逻上下文.已暂停:
            current_goal = self._构建巡逻状态目标(self._巡逻上下文)
            if asyncio.get_running_loop().time() < self._巡逻上下文.等待截止时间:
                self._更新导航状态("running", current_goal, 0.0, None)
                return
            self._巡逻上下文.等待截止时间 = None
            await self._推进巡逻路线()
            return

        if not await self._确保基础桥接运行():
            if self._导航上下文 is not None:
                self._标记导航失败("ROS bringup 未运行")
            if self._巡逻上下文 is not None:
                self._标记巡逻失败("ROS bringup 未运行")
            return

        try:
            bridge_status = await self.ros导航桥客户端.获取导航状态(timeout_sec=1.0)
        except ROS导航桥错误 as exc:
            if self._导航上下文 is not None:
                self._标记导航失败(exc.message)
            if self._巡逻上下文 is not None:
                self._标记巡逻失败(exc.message)
            return

        if self._巡逻上下文 is not None:
            await self._同步巡逻桥接状态(bridge_status)
            return
        self._应用导航桥状态(bridge_status)
        await self._同步动作桥接状态()

    async def _同步动作桥接状态(self) -> None:
        try:
            control_state = await self.ros导航桥客户端.获取控制状态(timeout_sec=1.0)
        except ROS导航桥错误:
            return

        action_payload = control_state.get("action")
        if not isinstance(action_payload, dict):
            return
        action_name = self._解析可选字符串值(action_payload.get("action_name"))
        status = self._解析可选字符串值(action_payload.get("status")) or "idle"
        source = self._解析可选字符串值(action_payload.get("source"))
        action_id = self._解析可选字符串值(action_payload.get("action_id"))
        parameters = action_payload.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}
        updated_at = self._解析可选整数(action_payload.get("updated_at")) or self._当前时间戳毫秒()
        self._更新动作控制状态(
            动作控制状态(
                动作名称=action_name,
                状态=status,
                来源=source,
                参数=parameters,
                动作ID=action_id,
                更新时间戳毫秒=updated_at,
            )
        )
        if status in {"pending", "running"}:
            if self._当前动作请求 is None and action_name and action_id:
                self._当前动作请求 = 动作执行请求(
                    动作名称=action_name,
                    来源=source or "runtime",
                    参数=parameters,
                    动作ID=action_id,
                )
            self._刷新控制域仲裁()
            return

        if self._当前动作请求 is not None and (action_id is None or self._当前动作请求.动作ID == action_id):
            self._当前动作请求 = None
        self._刷新控制域仲裁()

    async def 处理ROS进程退出(self, name: str, exit_code: int, expected: bool) -> None:
        """处理 ROS 进程退出事件。"""
        self._更新激光雷达状态()
        if expected:
            return

        message = f"ROS 进程异常退出: {name}, exit_code={exit_code}"
        snapshot = self._获取快照()
        if name == "mapping":
            self._更新建图状态("error", 当前地图=snapshot.建图.当前地图)
            self._更新任务状态("error", "mapping", snapshot.任务.任务ID)
            return
        if name == "bringup":
            if snapshot.任务.任务类型 == "mapping" or self.ros进程服务.是否运行("mapping"):
                self._更新建图状态("error", 当前地图=snapshot.建图.当前地图)
                self._更新任务状态("error", "mapping", snapshot.任务.任务ID)
            if snapshot.定位.状态 == "running":
                self._更新定位状态("error", 地图名称=snapshot.定位.地图名称)
        if name in {"bringup", "localization", "navigation"}:
            if self._导航上下文 is not None:
                self._标记导航失败(message)
            if self._巡逻上下文 is not None:
                self._标记巡逻失败(message)
            if self._导航上下文 is None and self._巡逻上下文 is None:
                self._更新导航状态("error", snapshot.导航.当前目标, None, message)
                if name == "localization":
                    self._更新定位状态("error", 地图名称=snapshot.定位.地图名称)

    async def 关闭(self) -> None:
        """关闭控制服务。"""
        self._导航上下文 = None
        self._巡逻上下文 = None
        await self.ros进程服务.关闭()
        self._更新激光雷达状态()
        snapshot = self._获取快照()
        self._更新建图状态("idle", 当前地图="", 最近地图=snapshot.建图.最近地图)
        self._更新定位状态("idle", 地图名称=snapshot.定位.地图名称)
        self._更新导航状态("idle", None, None, None)
        self._更新任务状态("idle", None, None)

    def _解析巡逻地图名称(self, route: 巡逻路线) -> str | None:
        if route.地图名称:
            return route.地图名称
        for waypoint in route.路点列表:
            if waypoint.地图名称:
                return waypoint.地图名称

        snapshot = self._获取快照()
        if snapshot.定位.地图名称:
            return snapshot.定位.地图名称
        if snapshot.建图.最近地图:
            return snapshot.建图.最近地图
        return self.默认地图配置

    def _补齐巡逻路线地图(self, route: 巡逻路线, map_name: str) -> 巡逻路线:
        waypoints = [
            replace(waypoint, 地图名称=map_name)
            for waypoint in route.路点列表
        ]
        return replace(route, 地图名称=map_name, 路点列表=waypoints)

    def _当前巡逻路点等待秒数(self, ctx: 巡逻上下文) -> float:
        waypoint = ctx.路线.路点列表[ctx.当前路点索引]
        if waypoint.到点等待秒数 is not None:
            return max(0.0, waypoint.到点等待秒数)
        if ctx.路线.默认到点等待秒数 > 0:
            return ctx.路线.默认到点等待秒数
        return max(0.0, self.巡逻默认等待秒数)

    def _构建巡逻状态目标(self, ctx: 巡逻上下文) -> dict[str, Any]:
        waypoint = ctx.路线.路点列表[ctx.当前路点索引]
        return {
            "id": ctx.当前目标ID or f"{ctx.任务ID}-wp-{ctx.当前路点索引 + 1}",
            "name": waypoint.名称,
            "map_name": waypoint.地图名称 or ctx.路线.地图名称,
            "frame_id": waypoint.坐标系,
            "x": waypoint.x,
            "y": waypoint.y,
            "yaw": waypoint.yaw,
            "waypoint_index": ctx.当前路点索引,
            "waypoint_total": len(ctx.路线.路点列表),
            "lap": ctx.已完成圈数 + 1,
        }

    def _构建巡逻导航目标(self, ctx: 巡逻上下文) -> 导航目标:
        waypoint = ctx.路线.路点列表[ctx.当前路点索引]
        goal_id = f"{ctx.任务ID}-lap{ctx.已完成圈数 + 1}-wp{ctx.当前路点索引 + 1}"
        return 导航目标(
            x=waypoint.x,
            y=waypoint.y,
            yaw=waypoint.yaw,
            frame_id=waypoint.坐标系,
            地图名称=waypoint.地图名称 or ctx.路线.地图名称,
            目标ID=goal_id,
        )

    async def _派发巡逻当前路点(self) -> 命令执行结果:
        ctx = self._巡逻上下文
        if ctx is None:
            return 命令执行结果.失败结果("patrol_not_active", "当前没有巡逻上下文")

        goal = self._构建巡逻导航目标(ctx)
        try:
            bridge = await self._发送导航目标到桥(goal)
        except ROS导航桥错误 as exc:
            self._标记巡逻失败(exc.message)
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        ctx.当前目标ID = goal.目标ID
        ctx.等待截止时间 = None
        ctx.上次桥接状态 = "pending"
        ctx.已暂停 = False
        self._更新任务状态("running", "patrol", ctx.任务ID)
        self._更新导航状态("pending", self._构建巡逻状态目标(ctx), None, None)
        return 命令执行结果.成功结果(
            "巡逻路点已下发",
            {
                "task_id": ctx.任务ID,
                "goal": self._构建巡逻状态目标(ctx),
                "bridge": bridge,
            },
        )

    async def _推进巡逻路线(self) -> 命令执行结果:
        ctx = self._巡逻上下文
        if ctx is None:
            return 命令执行结果.失败结果("patrol_not_active", "当前没有巡逻上下文")

        if ctx.当前路点索引 >= len(ctx.路线.路点列表) - 1:
            if ctx.路线.循环执行:
                ctx.当前路点索引 = 0
                ctx.已完成圈数 += 1
                return await self._派发巡逻当前路点()

            final_goal = self._构建巡逻状态目标(ctx)
            task_id = ctx.任务ID
            self._巡逻上下文 = None
            self._更新导航状态("succeeded", final_goal, 0.0, None)
            self._更新任务状态("idle", None, None)
            return 命令执行结果.成功结果(
                "巡逻已完成",
                {
                    "task_id": task_id,
                    "route_name": ctx.路线.名称,
                    "goal": final_goal,
                },
            )

        ctx.当前路点索引 += 1
        return await self._派发巡逻当前路点()

    async def _暂停导航任务(self) -> 命令执行结果:
        ctx = self._导航上下文
        if ctx is None:
            return 命令执行结果.失败结果("navigation_not_active", "当前没有活动导航任务")
        if ctx.已暂停:
            return 命令执行结果.成功结果("导航任务已处于暂停状态", {"task_id": ctx.任务ID})

        try:
            bridge = await self._取消导航桥目标(ignore_goal_missing=True)
        except ROS导航桥错误 as exc:
            return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        ctx.已暂停 = True
        self._更新任务状态("paused", "navigation", ctx.任务ID)
        self._更新导航状态("paused", ctx.目标.导出字典(), None, None)
        return 命令执行结果.成功结果("导航任务已暂停", {"task_id": ctx.任务ID, "bridge": bridge})

    async def _恢复导航任务(self) -> 命令执行结果:
        ctx = self._导航上下文
        if ctx is None:
            return 命令执行结果.失败结果("navigation_not_active", "当前没有可恢复的导航任务")
        if not ctx.已暂停:
            return 命令执行结果.失败结果("navigation_not_paused", "当前导航任务未暂停")

        try:
            env = await self._确保导航环境就绪(ctx.目标.地图名称 or "")
            bridge = await self._发送导航目标到桥(ctx.目标)
        except (ROS进程服务错误, ROS导航桥错误, ValueError, FileNotFoundError) as exc:
            error_code = getattr(exc, "code", "navigation_resume_failed")
            return 命令执行结果.失败结果(error_code, str(exc))

        ctx.已暂停 = False
        self._更新任务状态("running", "navigation", ctx.任务ID)
        self._更新导航状态("pending", ctx.目标.导出字典(), None, None)
        return 命令执行结果.成功结果(
            "导航任务已恢复",
            {
                "task_id": ctx.任务ID,
                "bridge": bridge,
                "environment": env,
            },
        )

    async def _终止导航任务(self) -> 命令执行结果:
        ctx = self._导航上下文
        if ctx is None:
            return 命令执行结果.失败结果("navigation_not_active", "当前没有活动导航任务")

        bridge: dict[str, Any] | None = None
        if not ctx.已暂停:
            try:
                bridge = await self._取消导航桥目标(ignore_goal_missing=True)
            except ROS导航桥错误 as exc:
                return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        self._导航上下文 = None
        self._更新任务状态("idle", None, None)
        self._更新导航状态("cancelled", ctx.目标.导出字典(), None, None)
        return 命令执行结果.成功结果("导航任务已终止", {"task_id": ctx.任务ID, "bridge": bridge})

    async def _暂停巡逻任务(self) -> 命令执行结果:
        ctx = self._巡逻上下文
        if ctx is None:
            return 命令执行结果.失败结果("patrol_not_active", "当前没有活动巡逻任务")
        if ctx.已暂停:
            return 命令执行结果.成功结果("巡逻任务已处于暂停状态", {"task_id": ctx.任务ID})

        bridge: dict[str, Any] | None = None
        if ctx.等待截止时间 is None:
            try:
                bridge = await self._取消导航桥目标(ignore_goal_missing=True)
            except ROS导航桥错误 as exc:
                return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        ctx.已暂停 = True
        self._更新任务状态("paused", "patrol", ctx.任务ID)
        self._更新导航状态("paused", self._构建巡逻状态目标(ctx), None, None)
        return 命令执行结果.成功结果("巡逻任务已暂停", {"task_id": ctx.任务ID, "bridge": bridge})

    async def _恢复巡逻任务(self) -> 命令执行结果:
        ctx = self._巡逻上下文
        if ctx is None:
            return 命令执行结果.失败结果("patrol_not_active", "当前没有可恢复的巡逻任务")
        if not ctx.已暂停:
            return 命令执行结果.失败结果("patrol_not_paused", "当前巡逻任务未暂停")

        try:
            env = await self._确保导航环境就绪(ctx.路线.地图名称 or "")
        except (ROS进程服务错误, ROS导航桥错误, ValueError, FileNotFoundError) as exc:
            error_code = getattr(exc, "code", "patrol_resume_failed")
            return 命令执行结果.失败结果(error_code, str(exc))

        ctx.已暂停 = False
        self._更新任务状态("running", "patrol", ctx.任务ID)
        if ctx.等待截止时间 is not None:
            self._更新导航状态("running", self._构建巡逻状态目标(ctx), 0.0, None)
            return 命令执行结果.成功结果(
                "巡逻任务已恢复",
                {
                    "task_id": ctx.任务ID,
                    "environment": env,
                    "waiting": True,
                },
            )

        dispatch_result = await self._派发巡逻当前路点()
        if not dispatch_result.成功:
            return dispatch_result
        return 命令执行结果.成功结果(
            "巡逻任务已恢复",
            {
                "task_id": ctx.任务ID,
                "environment": env,
                "dispatch": dispatch_result.数据,
            },
        )

    async def _终止巡逻任务(self) -> 命令执行结果:
        ctx = self._巡逻上下文
        if ctx is None:
            return 命令执行结果.失败结果("patrol_not_active", "当前没有活动巡逻任务")

        bridge: dict[str, Any] | None = None
        if ctx.等待截止时间 is None and not ctx.已暂停:
            try:
                bridge = await self._取消导航桥目标(ignore_goal_missing=True)
            except ROS导航桥错误 as exc:
                return 命令执行结果.失败结果(exc.code, exc.message, {"details": exc.details})

        final_goal = self._构建巡逻状态目标(ctx)
        self._巡逻上下文 = None
        self._更新任务状态("idle", None, None)
        self._更新导航状态("cancelled", final_goal, None, None)
        return 命令执行结果.成功结果("巡逻任务已终止", {"task_id": ctx.任务ID, "bridge": bridge})

    async def _同步巡逻桥接状态(self, bridge_status: dict[str, Any]) -> None:
        ctx = self._巡逻上下文
        if ctx is None:
            return
        if ctx.已暂停:
            self._更新任务状态("paused", "patrol", ctx.任务ID)
            self._更新导航状态("paused", self._构建巡逻状态目标(ctx), None, None)
            return

        state = self._标准化导航桥状态(bridge_status.get("state"))
        current_goal = self._构建巡逻状态目标(ctx)
        remaining_distance = self._解析可选浮点(bridge_status.get("remaining_distance"))
        failure_reason = self._解析可选字符串值(bridge_status.get("failure_reason"))
        ctx.上次桥接状态 = state

        if state in {"pending", "running"}:
            self._更新任务状态("running", "patrol", ctx.任务ID)
            self._更新导航状态(state, current_goal, remaining_distance, None)
            return

        if state == "succeeded":
            wait_sec = self._当前巡逻路点等待秒数(ctx)
            if wait_sec > 0:
                if ctx.等待截止时间 is None:
                    ctx.等待截止时间 = asyncio.get_running_loop().time() + wait_sec
                self._更新导航状态("running", current_goal, 0.0, None)
                return
            await self._推进巡逻路线()
            return

        if state == "cancelled":
            self._标记巡逻失败("巡逻导航被取消")
            return

        if state == "error":
            self._标记巡逻失败(failure_reason or "巡逻导航失败")
            return

        self._更新导航状态(state, current_goal, remaining_distance, failure_reason)

    def _应用导航桥状态(self, bridge_status: dict[str, Any]) -> None:
        state = self._标准化导航桥状态(bridge_status.get("state"))
        current_goal = bridge_status.get("current_goal")
        if not isinstance(current_goal, dict):
            current_goal = None
        remaining_distance = self._解析可选浮点(bridge_status.get("remaining_distance"))
        failure_reason = self._解析可选字符串值(bridge_status.get("failure_reason"))

        if self._导航上下文 is not None and self._导航上下文.已暂停:
            self._更新任务状态("paused", "navigation", self._导航上下文.任务ID)
            self._更新导航状态("paused", self._导航上下文.目标.导出字典(), None, None)
            return

        if self._导航上下文 is None:
            self._更新导航状态(state, current_goal, remaining_distance, failure_reason)
            return

        task_goal = current_goal or self._导航上下文.目标.导出字典()
        task_id = self._导航上下文.任务ID
        if state in {"pending", "running"}:
            self._更新任务状态("running", "navigation", task_id)
            self._更新导航状态(state, task_goal, remaining_distance, None)
            return

        if state == "succeeded":
            self._导航上下文 = None
            self._更新任务状态("idle", None, None)
            self._更新导航状态("succeeded", task_goal, 0.0, None)
            return

        if state == "cancelled":
            self._导航上下文 = None
            self._更新任务状态("idle", None, None)
            self._更新导航状态("cancelled", task_goal, None, None)
            return

        if state == "error":
            self._标记导航失败(failure_reason or "导航失败", task_goal)
            return

        self._更新导航状态(state, task_goal, remaining_distance, failure_reason)

    def _标记导航失败(self, message: str, goal: dict[str, Any] | None = None) -> None:
        task_id = self._导航上下文.任务ID if self._导航上下文 is not None else None
        current_goal = goal or (self._导航上下文.目标.导出字典() if self._导航上下文 is not None else self._获取快照().导航.当前目标)
        self._导航上下文 = None
        self._更新导航状态("error", current_goal, None, message)
        self._更新任务状态("error", "navigation", task_id)
        logger.warning("导航任务失败: %s", message)

    def _标记巡逻失败(self, message: str) -> None:
        task_id = self._巡逻上下文.任务ID if self._巡逻上下文 is not None else None
        current_goal = self._构建巡逻状态目标(self._巡逻上下文) if self._巡逻上下文 is not None else self._获取快照().导航.当前目标
        self._巡逻上下文 = None
        self._更新导航状态("error", current_goal, None, message)
        self._更新任务状态("error", "patrol", task_id)
        logger.warning("巡逻任务失败: %s", message)

    def _解析可选浮点(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _解析可选字符串值(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _解析可选整数(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _解析可选向量(self, value: Any, expected_len: int) -> tuple[float, ...] | None:
        if not isinstance(value, list) or len(value) < expected_len:
            return None
        result: list[float] = []
        try:
            for item in value[:expected_len]:
                result.append(float(item))
        except (TypeError, ValueError):
            return None
        return tuple(result)

    def _从四元数解析偏航角(self, quaternion_xyzw: tuple[float, ...]) -> float | None:
        if len(quaternion_xyzw) < 4:
            return None
        x, y, z, w = quaternion_xyzw[:4]
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)


__all__ = [
    "命令执行结果",
    "导航目标",
    "运行时控制服务",
]
