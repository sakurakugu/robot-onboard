from __future__ import annotations

import importlib
import json
import platform
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, String
from tf2_ros import TransformBroadcaster


@dataclass
class 速度命令:
    """缓存最近一次速度指令。"""

    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0
    时间戳: float = 0.0

    def 导出元组(self) -> tuple[float, float, float]:
        """导出为元组。"""
        return (self.vx, self.vy, self.wz)


class 机器狗桥接节点(Node):
    """负责把机器狗遥测和速度控制桥接到 ROS2。"""

    def __init__(self) -> None:
        super().__init__("sparkrobot_dog_bridge")

        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("imu_topic", "/imu")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("dog_state_topic", "/sparkrobot/dog_state")
        self.declare_parameter("feedback_topic", "/sparkrobot/feedback")
        self.declare_parameter("navigation_state_topic", "/sparkrobot/navigation_state")
        self.declare_parameter("bridge_status_topic", "/sparkrobot/bridge_status")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("telemetry_url", "http://127.0.0.1:8080/api/v1/telemetry/full")
        self.declare_parameter("telemetry_timeout_sec", 1.0)
        self.declare_parameter("telemetry_poll_hz", 20.0)
        self.declare_parameter("status_hz", 5.0)
        self.declare_parameter("report_bridge_status_to_server", True)
        self.declare_parameter("telemetry_udp_host", "127.0.0.1")
        self.declare_parameter("telemetry_udp_port", 8080)
        self.declare_parameter("telemetry_offline_timeout_sec", 1.5)
        self.declare_parameter("stop_on_telemetry_offline", True)
        self.declare_parameter("publish_tf", True)
        self.declare_parameter("enable_motion_control", True)
        self.declare_parameter("auto_stand_up_on_startup", False)
        self.declare_parameter("stand_up_wait_sec", 3.0)
        self.declare_parameter("command_hz", 15.0)
        self.declare_parameter("command_timeout_sec", 0.5)
        self.declare_parameter("emergency_stop_topic", "/sparkrobot/emergency_stop")
        self.declare_parameter("action_command_topic", "/sparkrobot/action_command")
        self.declare_parameter("action_state_topic", "/sparkrobot/action_state")
        self.declare_parameter("direct_control_topic", "/sparkrobot/direct_control")
        self.declare_parameter("max_linear_x", 0.6)
        self.declare_parameter("max_linear_y", 0.4)
        self.declare_parameter("max_angular_z", 1.2)
        self.declare_parameter("max_accel_x", 0.8)
        self.declare_parameter("max_accel_y", 0.6)
        self.declare_parameter("max_accel_z", 1.5)
        self.declare_parameter("rotate_in_place_enabled", True)
        self.declare_parameter("rotate_in_place_angular_threshold", 0.35)
        self.declare_parameter("rotate_in_place_linear_deadband", 0.05)
        self.declare_parameter("sdk_local_ip", "127.0.0.1")
        self.declare_parameter("sdk_local_port", 43988)
        self.declare_parameter("sdk_dog_ip", "127.0.0.1")

        self._base_frame = self._读取字符串参数("base_frame", "base_link")
        self._odom_frame = self._读取字符串参数("odom_frame", "odom")
        self._telemetry_url = self._读取字符串参数("telemetry_url", "http://127.0.0.1:8080/api/v1/telemetry/full")
        self._telemetry_timeout_sec = self._读取浮点参数("telemetry_timeout_sec", 1.0)
        self._回灌桥接状态到服务端 = self._读取布尔参数("report_bridge_status_to_server", True)
        self._遥测UDP主机 = self._读取字符串参数("telemetry_udp_host", "127.0.0.1")
        self._遥测UDP端口 = self._读取整数参数("telemetry_udp_port", 8080)
        self._遥测离线超时秒数 = self._读取浮点参数("telemetry_offline_timeout_sec", 1.5)
        self._遥测离线时停止运动 = self._读取布尔参数("stop_on_telemetry_offline", True)
        self._command_timeout_sec = self._读取浮点参数("command_timeout_sec", 0.5)
        self._publish_tf = self._读取布尔参数("publish_tf", True)
        self._enable_motion_control = self._读取布尔参数("enable_motion_control", True)
        self._启动后自动站立 = self._读取布尔参数("auto_stand_up_on_startup", False)
        self._站立等待秒数 = self._读取浮点参数("stand_up_wait_sec", 3.0)
        self._最大线速度x = self._读取浮点参数("max_linear_x", 0.6)
        self._最大线速度y = self._读取浮点参数("max_linear_y", 0.4)
        self._最大角速度z = self._读取浮点参数("max_angular_z", 1.2)
        self._最大加速度x = self._读取浮点参数("max_accel_x", 0.8)
        self._最大加速度y = self._读取浮点参数("max_accel_y", 0.6)
        self._最大加速度z = self._读取浮点参数("max_accel_z", 1.5)
        self._启用原地转向 = self._读取布尔参数("rotate_in_place_enabled", True)
        self._原地转向角速度阈值 = self._读取浮点参数("rotate_in_place_angular_threshold", 0.35)
        self._原地转向线速度死区 = self._读取浮点参数("rotate_in_place_linear_deadband", 0.05)

        self._imu_publisher = self.create_publisher(Imu, self._读取字符串参数("imu_topic", "/imu"), 10)
        self._odom_publisher = self.create_publisher(Odometry, self._读取字符串参数("odom_topic", "/odom"), 10)
        self._dog_state_publisher = self.create_publisher(String, self._读取字符串参数("dog_state_topic", "/sparkrobot/dog_state"), 10)
        self._feedback_publisher = self.create_publisher(String, self._读取字符串参数("feedback_topic", "/sparkrobot/feedback"), 10)
        self._navigation_state_publisher = self.create_publisher(
            String,
            self._读取字符串参数("navigation_state_topic", "/sparkrobot/navigation_state"),
            10,
        )
        self._bridge_status_publisher = self.create_publisher(
            String,
            self._读取字符串参数("bridge_status_topic", "/sparkrobot/bridge_status"),
            10,
        )
        self._action_state_publisher = self.create_publisher(
            String,
            self._读取字符串参数("action_state_topic", "/sparkrobot/action_state"),
            10,
        )
        self._tf_broadcaster = TransformBroadcaster(self)

        self.create_subscription(Twist, self._读取字符串参数("cmd_vel_topic", "/cmd_vel"), self._处理速度指令, 10)
        self.create_subscription(
            Bool,
            self._读取字符串参数("emergency_stop_topic", "/sparkrobot/emergency_stop"),
            self._处理急停指令,
            10,
        )
        self.create_subscription(
            String,
            self._读取字符串参数("action_command_topic", "/sparkrobot/action_command"),
            self._处理动作命令,
            10,
        )
        self.create_subscription(
            String,
            self._读取字符串参数("direct_control_topic", "/sparkrobot/direct_control"),
            self._处理直连控制命令,
            10,
        )

        self._最近速度命令 = 速度命令()
        self._当前输出速度 = (0.0, 0.0, 0.0)
        self._上次遥测错误日志时间 = 0.0
        self._上次控制错误日志时间 = 0.0
        self._最近遥测成功时间 = 0.0
        self._遥测在线 = False
        self._当前急停 = False
        self._最近反馈: dict[str, Any] = {}
        self._当前裁决目标速度 = (0.0, 0.0, 0.0)
        self._当前速度裁决原因 = "initializing"
        self._上次控制裁决原因: str | None = None
        self._机器狗SDK: Any | None = None
        self._SDK实例: Any | None = None
        self._遥测回灌套接字: socket.socket | None = None
        self._动作状态锁 = threading.RLock()
        self._动作取消事件 = threading.Event()
        self._动作执行线程: threading.Thread | None = None
        self._动作执行令牌 = 0
        self._动作状态: dict[str, Any] = self._构建初始动作状态()

        self._初始化SDK()
        self._初始化遥测回灌()
        self._创建定时器()
        self._发布动作状态()
        self.get_logger().info(
            "机器狗桥接节点已启动: "
            f"telemetry_url={self._telemetry_url} "
            f"motion_control={self._enable_motion_control} "
            f"sdk_ready={self._SDK实例 is not None}"
        )

    def _创建定时器(self) -> None:
        telemetry_period = 1.0 / max(1.0, self._读取浮点参数("telemetry_poll_hz", 20.0))
        command_period = 1.0 / max(1.0, self._读取浮点参数("command_hz", 15.0))
        status_period = 1.0 / max(1.0, self._读取浮点参数("status_hz", 5.0))
        self._控制周期秒数 = command_period
        self._上次控制周期时间 = time.time()
        self._telemetry_timer = self.create_timer(telemetry_period, self._拉取遥测并发布)
        self._command_timer = self.create_timer(command_period, self._发送速度命令)
        self._status_timer = self.create_timer(status_period, self._发布桥接状态)

    def _初始化SDK(self) -> None:
        if not self._enable_motion_control:
            self.get_logger().info("已禁用机器狗速度控制输出")
            return

        try:
            self._机器狗SDK = self._加载SDK模块()
            self._SDK实例 = self._机器狗SDK.HighLevel()
            self._SDK实例.initRobot(
                self._读取字符串参数("sdk_local_ip", "127.0.0.1"),
                self._读取整数参数("sdk_local_port", 43988),
                self._读取字符串参数("sdk_dog_ip", "127.0.0.1"),
            )
            if self._启动后自动站立:
                self._尝试自动站立()
        except Exception as exc:
            self._SDK实例 = None
            self.get_logger().warning(f"机器狗 SDK 初始化失败，后续仅发布状态不下发速度: {exc}")

    def _初始化遥测回灌(self) -> None:
        if not self._回灌桥接状态到服务端:
            return
        try:
            self._遥测回灌套接字 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as exc:
            self._遥测回灌套接字 = None
            self.get_logger().warning(f"初始化桥接状态回灌 UDP 套接字失败: {exc}")

    def _加载SDK模块(self) -> Any:
        arch = "aarch64" if ("aarch64" in platform.machine().lower() or "arm64" in platform.machine().lower()) else "x86_64"
        lib_dir = Path(__file__).resolve().parent / "vendor" / "lib" / "zsl-1" / arch
        if not lib_dir.exists():
            raise FileNotFoundError(f"未找到 SDK 动态库目录: {lib_dir}")

        lib_dir_text = str(lib_dir)
        if lib_dir_text not in sys.path:
            sys.path.insert(0, lib_dir_text)
        return importlib.import_module("mc_sdk_zsl_1_py")

    def _尝试自动站立(self) -> None:
        if self._SDK实例 is None:
            return

        try:
            current_mode = self._读取当前控制模式()
            if current_mode == 18:
                self.get_logger().info("SDK 当前已处于移动模式，跳过自动站立")
                return

            self.get_logger().info(f"准备执行自动站立，当前控制模式={current_mode}")
            self._SDK实例.standUp()
            wait_sec = max(0.0, self._站立等待秒数)
            if wait_sec > 0.0:
                time.sleep(wait_sec)
            self.get_logger().info(f"自动站立完成，当前控制模式={self._读取当前控制模式()}")
        except Exception as exc:
            self.get_logger().warning(f"自动站立失败: {exc}")

    def _读取当前控制模式(self) -> int | None:
        if self._SDK实例 is None or not hasattr(self._SDK实例, "getCurrentCtrlmode"):
            return None
        try:
            return int(self._SDK实例.getCurrentCtrlmode())
        except Exception:
            return None

    def _处理速度指令(self, msg: Twist) -> None:
        if self._当前急停:
            return

        self._最近速度命令 = 速度命令(
            vx=self._限幅(float(msg.linear.x), self._最大线速度x),
            vy=self._限幅(float(msg.linear.y), self._最大线速度y),
            wz=self._限幅(float(msg.angular.z), self._最大角速度z),
            时间戳=time.time(),
        )

    def _处理急停指令(self, msg: Bool) -> None:
        新状态 = bool(msg.data)
        if 新状态 == self._当前急停:
            return

        self._当前急停 = 新状态
        if 新状态:
            self._最近速度命令 = 速度命令()
            self._取消当前动作("emergency_stop")
            self.get_logger().warning("收到急停信号，已清空缓存速度指令")
            return

        self.get_logger().info("急停已解除，等待新的速度指令")

    def _处理动作命令(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"解析动作命令失败: {exc}")
            return

        if not isinstance(payload, dict):
            self.get_logger().warning("动作命令格式无效，必须为 JSON 对象")
            return

        command_type = str(payload.get("type") or "").strip()
        if command_type == "execute":
            self._接收执行动作命令(payload)
            return
        if command_type == "cancel":
            self._接收取消动作命令(payload)
            return

        self.get_logger().warning(f"未知动作命令类型: {command_type}")

    def _处理直连控制命令(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"解析直连控制命令失败: {exc}")
            return

        if not isinstance(payload, dict):
            self.get_logger().warning("直连控制命令格式无效，必须为 JSON 对象")
            return
        if self._SDK实例 is None:
            self.get_logger().warning("机器狗 SDK 未就绪，忽略直连控制命令")
            return

        control_type = str(payload.get("type") or "").strip()
        if not control_type:
            self.get_logger().warning("直连控制命令缺少 type")
            return

        if control_type == "estop":
            action_id = str(payload.get("action_id") or f"direct-estop-{int(time.time() * 1000)}")
            source = str(payload.get("source") or "runtime").strip() or "runtime"
            self._立即执行急停动作(action_id, source, {})
            return

        self._取消当前动作("direct_control_preempt")
        self._最近速度命令 = 速度命令()
        self._当前输出速度 = (0.0, 0.0, 0.0)
        try:
            if control_type == "move":
                self._SDK实例.move(
                    float(payload.get("vx", 0.0) or 0.0),
                    float(payload.get("vy", 0.0) or 0.0),
                    float(payload.get("yaw_rate", 0.0) or 0.0),
                )
                return
            if control_type == "two_leg":
                self._SDK实例.twoLegStand(
                    float(payload.get("vx", 0.0) or 0.0),
                    float(payload.get("yaw_rate", 0.0) or 0.0),
                )
                return
            if control_type == "attitude":
                self._SDK实例.attitudeControl(
                    float(payload.get("roll_rate", 0.0) or 0.0),
                    float(payload.get("pitch_rate", 0.0) or 0.0),
                    float(payload.get("yaw_rate", 0.0) or 0.0),
                    float(payload.get("height_vel", 0.0) or 0.0),
                )
                return
        except Exception as exc:
            self.get_logger().warning(f"执行直连控制失败: type={control_type}, error={exc}")
            return

        self.get_logger().warning(f"未知直连控制类型: {control_type}")

    def _接收执行动作命令(self, payload: dict[str, Any]) -> None:
        action_name = str(payload.get("action_name") or "").strip()
        action_id = str(payload.get("action_id") or "").strip()
        parameters = payload.get("parameters", {})
        source = str(payload.get("source") or "runtime").strip() or "runtime"
        if not action_name or not action_id:
            self.get_logger().warning("动作命令缺少 action_name 或 action_id")
            return
        if not isinstance(parameters, dict):
            self.get_logger().warning("动作命令 parameters 必须是对象")
            return
        if self._当前急停 and action_name != "estop":
            self._更新动作状态(
                状态="error",
                动作ID=action_id,
                动作名称=action_name,
                来源=source,
                参数=parameters,
                错误码="emergency_stop_active",
                消息="当前处于急停状态，无法执行动作",
                激活=False,
            )
            return
        if self._SDK实例 is None:
            self._更新动作状态(
                状态="error",
                动作ID=action_id,
                动作名称=action_name,
                来源=source,
                参数=parameters,
                错误码="sdk_unavailable",
                消息="机器狗 SDK 未就绪，无法执行动作",
                激活=False,
            )
            return
        if action_name == "estop":
            self._立即执行急停动作(action_id, source, parameters)
            return
        with self._动作状态锁:
            if self._动作执行线程 is not None and self._动作执行线程.is_alive():
                self._更新动作状态(
                    状态="error",
                    动作ID=action_id,
                    动作名称=action_name,
                    来源=source,
                    参数=parameters,
                    错误码="action_busy",
                    消息="当前已有动作正在执行",
                    激活=True,
                )
                return
            self._动作执行令牌 += 1
            token = self._动作执行令牌
            self._动作取消事件.clear()
            self._动作执行线程 = threading.Thread(
                target=self._执行动作线程,
                args=(token, action_id, action_name, source, dict(parameters)),
                daemon=True,
                name="sparkrobot-dog-action",
            )
            self._更新动作状态(
                状态="pending",
                动作ID=action_id,
                动作名称=action_name,
                来源=source,
                参数=parameters,
                消息="动作已受理，等待执行",
                激活=True,
            )
            self._动作执行线程.start()

    def _立即执行急停动作(self, action_id: str, source: str, parameters: dict[str, Any]) -> None:
        """急停必须抢占执行，不能被普通动作忙状态拦住。"""
        if self._SDK实例 is None:
            self._更新动作状态(
                状态="error",
                动作ID=action_id,
                动作名称="estop",
                来源=source,
                参数=parameters,
                错误码="sdk_unavailable",
                消息="机器狗 SDK 未就绪，无法执行急停",
                激活=False,
            )
            return
        self._取消当前动作("estop_preempt")
        self._最近速度命令 = 速度命令()
        self._更新动作状态(
            状态="running",
            动作ID=action_id,
            动作名称="estop",
            来源=source,
            参数=parameters,
            消息="急停执行中",
            激活=True,
        )
        try:
            self.get_logger().warning("执行急停: 直接 passive()")
            self._SDK实例.passive()
            time.sleep(0.1)
            self._更新动作状态(
                状态="succeeded",
                动作ID=action_id,
                动作名称="estop",
                来源=source,
                参数=parameters,
                消息="急停执行成功",
                激活=False,
            )
        except Exception as exc:
            self.get_logger().warning(f"执行急停失败: {exc}")
            self._更新动作状态(
                状态="error",
                动作ID=action_id,
                动作名称="estop",
                来源=source,
                参数=parameters,
                错误码="action_exception",
                消息=str(exc),
                激活=False,
            )

    def _接收取消动作命令(self, payload: dict[str, Any]) -> None:
        reason = str(payload.get("reason") or "cancelled").strip() or "cancelled"
        self._取消当前动作(reason)

    def _执行动作线程(
        self,
        token: int,
        action_id: str,
        action_name: str,
        source: str,
        parameters: dict[str, Any],
    ) -> None:
        self._更新动作状态(
            状态="running",
            动作ID=action_id,
            动作名称=action_name,
            来源=source,
            参数=parameters,
            消息="动作执行中",
            激活=True,
        )
        try:
            success = self._执行动作(action_name, parameters, token)
            if self._动作已取消(token):
                self._更新动作状态(
                    状态="cancelled",
                    动作ID=action_id,
                    动作名称=action_name,
                    来源=source,
                    参数=parameters,
                    消息="动作已取消",
                    激活=False,
                )
            elif success:
                self._更新动作状态(
                    状态="succeeded",
                    动作ID=action_id,
                    动作名称=action_name,
                    来源=source,
                    参数=parameters,
                    消息="动作执行成功",
                    激活=False,
                )
            else:
                self._更新动作状态(
                    状态="error",
                    动作ID=action_id,
                    动作名称=action_name,
                    来源=source,
                    参数=parameters,
                    错误码="action_failed",
                    消息="动作执行失败",
                    激活=False,
                )
        except Exception as exc:
            self.get_logger().warning(f"执行动作失败: action={action_name}, error={exc}")
            self._更新动作状态(
                状态="error",
                动作ID=action_id,
                动作名称=action_name,
                来源=source,
                参数=parameters,
                错误码="action_exception",
                消息=str(exc),
                激活=False,
            )
        finally:
            with self._动作状态锁:
                self._动作执行线程 = None

    def _执行动作(self, action_name: str, parameters: dict[str, Any], token: int) -> bool:
        if self._SDK实例 is None:
            return False
        if action_name == "stand_up":
            return self._执行站立动作(token)
        if action_name in {"sit_down", "lie_down"}:
            return self._执行趴下动作(token)
        if action_name == "jump":
            return self._执行定长动作(token, "跳跃", self._SDK实例.jump, 4.0)
        if action_name == "front_jump":
            return self._执行定长动作(token, "向前跳跃", self._SDK实例.frontJump, 4.0)
        if action_name == "back_flip":
            return self._执行定长动作(token, "后空翻", self._SDK实例.backflip, 4.0)
        if action_name in {"shake_hand", "wave"}:
            return self._执行定长动作(token, "握手", self._SDK实例.shakeHand, 4.0)
        if action_name in {"two_leg_once", "two_leg_stand"}:
            return self._执行双腿站立动作(token, action_name == "two_leg_once")
        if action_name == "cancel_two_leg_stand":
            return self._执行定长动作(token, "退出双腿站立", self._SDK实例.cancelTwoLegStand, 1.0)
        if action_name == "exit_lie_down":
            return self._执行趴下动作(token)
        if action_name == "exit_stand_up":
            return self._执行站立动作(token)
        if action_name == "exit_stop":
            return self._执行退出停止动作(token)
        if action_name == "estop":
            return self._执行定长动作(token, "急停趴下", self._SDK实例.passive, 1.0)
        raise ValueError(f"暂不支持的 dog_bridge 动作: {action_name}")

    def _执行站立动作(self, token: int) -> bool:
        if self._SDK实例 is None:
            return False
        current_mode = self._读取当前控制模式()
        if current_mode == 16:
            if not self._执行趴下动作(token):
                return False
        self.get_logger().info("执行动作: 站立")
        self._SDK实例.standUp()
        return self._可中断等待(token, 3.0)

    def _执行趴下动作(self, token: int) -> bool:
        if self._SDK实例 is None:
            return False
        self.get_logger().info("执行动作: 趴下")
        self._SDK实例.lieDown()
        return self._可中断等待(token, 3.0)

    def _执行双腿站立动作(self, token: int, once: bool) -> bool:
        if self._SDK实例 is None:
            return False
        self.get_logger().info("执行动作: 双腿站立")
        self._SDK实例.twoLegStand(0.0, 0.0)
        if not once:
            return True
        if not self._可中断等待(token, 4.0):
            return False
        self._SDK实例.cancelTwoLegStand()
        return self._可中断等待(token, 2.0)

    def _执行退出停止动作(self, token: int) -> bool:
        if self._SDK实例 is None:
            return False
        self.get_logger().info("执行动作: 退出停止")
        current_mode = self._读取当前控制模式()
        if current_mode != 16:
            self._SDK实例.lieDown()
            if not self._可中断等待(token, 2.0):
                return False
        self._SDK实例.passive()
        return self._可中断等待(token, 1.0)

    def _执行定长动作(self, token: int, label: str, callback: Any, wait_sec: float) -> bool:
        if self._SDK实例 is None:
            return False
        self.get_logger().info(f"执行动作: {label}")
        callback()
        return self._可中断等待(token, wait_sec)

    def _可中断等待(self, token: int, seconds: float) -> bool:
        deadline = time.time() + max(0.0, seconds)
        while time.time() < deadline:
            if self._动作已取消(token):
                self._停止当前动作()
                return False
            time.sleep(0.1)
        return not self._动作已取消(token)

    def _动作已取消(self, token: int) -> bool:
        return self._动作取消事件.is_set() or token != self._动作执行令牌

    def _取消当前动作(self, reason: str) -> None:
        with self._动作状态锁:
            self._动作执行令牌 += 1
            self._动作取消事件.set()
        self._停止当前动作()
        state = dict(self._动作状态)
        if not state.get("active"):
            return
        state_parameters = state.get("parameters")
        if not isinstance(state_parameters, dict):
            state_parameters = {}
        self._更新动作状态(
            状态="cancelled",
            动作ID=str(state.get("action_id") or ""),
            动作名称=str(state.get("action_name") or ""),
            来源=str(state.get("source") or "runtime"),
            参数=state_parameters,
            消息=f"动作已取消: {reason}",
            激活=False,
        )

    def _停止当前动作(self) -> None:
        if self._SDK实例 is None:
            return
        try:
            self._SDK实例.move(0.0, 0.0, 0.0)
        except Exception:
            pass
        try:
            self._SDK实例.cancelTwoLegStand()
        except Exception:
            pass

    def _构建初始动作状态(self) -> dict[str, Any]:
        return {
            "available": True,
            "active": False,
            "status": "idle",
            "action_id": None,
            "action_name": None,
            "source": None,
            "parameters": {},
            "error_code": None,
            "message": "",
            "updated_at": 0,
        }

    def _更新动作状态(
        self,
        状态: str,
        动作ID: str,
        动作名称: str,
        来源: str,
        参数: dict[str, Any],
        消息: str = "",
        错误码: str | None = None,
        激活: bool = False,
    ) -> None:
        with self._动作状态锁:
            self._动作状态 = {
                "available": True,
                "active": 激活,
                "status": 状态,
                "action_id": 动作ID or None,
                "action_name": 动作名称 or None,
                "source": 来源 or None,
                "parameters": dict(参数),
                "error_code": 错误码,
                "message": 消息,
                "updated_at": int(time.time() * 1000),
            }
        self._发布动作状态()

    def _发布动作状态(self) -> None:
        message = String()
        message.data = json.dumps(self._动作状态, ensure_ascii=False, separators=(",", ":"))
        self._action_state_publisher.publish(message)

    def _发送速度命令(self) -> None:
        current_time = time.time()
        控制步长 = self._计算控制步长(current_time)
        target, 裁决原因 = self._裁决目标速度(current_time)
        self._当前裁决目标速度 = target

        最终裁决原因 = 裁决原因
        if not self._enable_motion_control:
            output = (0.0, 0.0, 0.0)
            最终裁决原因 = "motion_control_disabled"
        elif self._SDK实例 is None:
            output = (0.0, 0.0, 0.0)
            最终裁决原因 = "sdk_unavailable"
        elif 裁决原因 == "normal":
            output = self._应用加速度限幅(target, self._当前输出速度, 控制步长)
        else:
            output = (0.0, 0.0, 0.0)

        self._当前速度裁决原因 = 最终裁决原因
        self._记录控制裁决(最终裁决原因)

        if self._SDK实例 is None or not self._enable_motion_control:
            return

        if self._速度近似相等(output, self._当前输出速度):
            return

        try:
            self._SDK实例.move(*output)
            self._当前输出速度 = output
        except Exception as exc:
            self._当前速度裁决原因 = "control_error"
            self._记录控制裁决("control_error")
            self._节流警告("control", f"发送机器狗速度命令失败: {exc}")

    def _拉取遥测并发布(self) -> None:
        try:
            payload = self._请求遥测快照()
        except Exception as exc:
            self._节流警告("telemetry", f"拉取机器狗遥测失败: {exc}")
            return

        if not isinstance(payload, dict):
            self._节流警告("telemetry", "遥测接口返回格式无效")
            return

        self._最近遥测成功时间 = time.time()
        self._遥测在线 = bool(payload.get("online", False))
        feedback = payload.get("feedback", {})
        if isinstance(feedback, dict):
            self._最近反馈 = feedback

        self._发布dog_state(payload)
        self._发布反馈状态(payload)
        self._发布导航状态(payload)
        self._发布IMU(payload)
        self._发布里程计与TF(payload)

    def _请求遥测快照(self) -> dict[str, Any]:
        request = urllib.request.Request(
            self._telemetry_url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=self._telemetry_timeout_sec) as response:
            body = response.read().decode("utf-8")
        message = json.loads(body)
        if not isinstance(message, dict) or not bool(message.get("success", False)):
            raise RuntimeError(f"遥测接口请求失败: {message}")
        data = message.get("data", {})
        if not isinstance(data, dict):
            raise RuntimeError("遥测接口 data 字段不是对象")
        return data

    def _发布dog_state(self, payload: dict[str, Any]) -> None:
        dog_state = payload.get("dog_state", {})
        if not isinstance(dog_state, dict):
            return
        message = String()
        message.data = json.dumps(
            {
                "online": payload.get("online", False),
                **dog_state,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._dog_state_publisher.publish(message)

    def _发布反馈状态(self, payload: dict[str, Any]) -> None:
        feedback = payload.get("feedback", {})
        if not isinstance(feedback, dict):
            return
        message = String()
        message.data = json.dumps(feedback, ensure_ascii=False, separators=(",", ":"))
        self._feedback_publisher.publish(message)

    def _发布导航状态(self, payload: dict[str, Any]) -> None:
        navigation_state = payload.get("navigation_state", {})
        if not isinstance(navigation_state, dict):
            return
        message = String()
        message.data = json.dumps(navigation_state, ensure_ascii=False, separators=(",", ":"))
        self._navigation_state_publisher.publish(message)

    def _发布IMU(self, payload: dict[str, Any]) -> None:
        imu_info = payload.get("imu_info", {})
        if not isinstance(imu_info, dict):
            return

        acc = self._读取向量(imu_info.get("acc"), 3)
        gyro = self._读取向量(imu_info.get("gyro"), 3)
        quat = self._读取向量(imu_info.get("quat"), 4)
        if acc is None or gyro is None or quat is None:
            return

        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._base_frame
        msg.linear_acceleration.x = acc[0]
        msg.linear_acceleration.y = acc[1]
        msg.linear_acceleration.z = acc[2]
        msg.angular_velocity.x = gyro[0]
        msg.angular_velocity.y = gyro[1]
        msg.angular_velocity.z = gyro[2]
        msg.orientation.w = quat[0]
        msg.orientation.x = quat[1]
        msg.orientation.y = quat[2]
        msg.orientation.z = quat[3]
        self._imu_publisher.publish(msg)

    def _发布里程计与TF(self, payload: dict[str, Any]) -> None:
        odom_info = payload.get("odom_info", {})
        if not isinstance(odom_info, dict):
            return

        position = self._读取向量(odom_info.get("position"), 3)
        linear_velocity = self._读取向量(odom_info.get("v_body"), 3)
        angular_velocity = self._读取向量(odom_info.get("omega_body"), 3)
        if position is None or linear_velocity is None or angular_velocity is None:
            return

        quaternion = self._解析姿态四元数(payload)
        if quaternion is None:
            quaternion = (0.0, 0.0, 0.0, 1.0)

        stamp = self.get_clock().now().to_msg()

        odom_msg = Odometry()
        odom_msg.header.stamp = stamp
        odom_msg.header.frame_id = self._odom_frame
        odom_msg.child_frame_id = self._base_frame
        odom_msg.pose.pose.position.x = position[0]
        odom_msg.pose.pose.position.y = position[1]
        odom_msg.pose.pose.position.z = position[2]
        odom_msg.pose.pose.orientation.x = quaternion[0]
        odom_msg.pose.pose.orientation.y = quaternion[1]
        odom_msg.pose.pose.orientation.z = quaternion[2]
        odom_msg.pose.pose.orientation.w = quaternion[3]
        odom_msg.twist.twist.linear.x = linear_velocity[0]
        odom_msg.twist.twist.linear.y = linear_velocity[1]
        odom_msg.twist.twist.linear.z = linear_velocity[2]
        odom_msg.twist.twist.angular.x = angular_velocity[0]
        odom_msg.twist.twist.angular.y = angular_velocity[1]
        odom_msg.twist.twist.angular.z = angular_velocity[2]
        self._odom_publisher.publish(odom_msg)

        if not self._publish_tf:
            return

        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = self._odom_frame
        transform.child_frame_id = self._base_frame
        transform.transform.translation.x = position[0]
        transform.transform.translation.y = position[1]
        transform.transform.translation.z = position[2]
        transform.transform.rotation.x = quaternion[0]
        transform.transform.rotation.y = quaternion[1]
        transform.transform.rotation.z = quaternion[2]
        transform.transform.rotation.w = quaternion[3]
        self._tf_broadcaster.sendTransform(transform)

    def _解析姿态四元数(self, payload: dict[str, Any]) -> tuple[float, float, float, float] | None:
        imu_info = payload.get("imu_info", {})
        if isinstance(imu_info, dict):
            quat = self._读取向量(imu_info.get("quat"), 4)
            if quat is not None:
                return (quat[1], quat[2], quat[3], quat[0])

        navigation_state = payload.get("navigation_state", {})
        if not isinstance(navigation_state, dict):
            return None
        current_pose = navigation_state.get("current_pose", {})
        if not isinstance(current_pose, dict):
            return None
        orientation = self._读取向量(current_pose.get("orientation"), 4)
        if orientation is None:
            return None
        return (orientation[0], orientation[1], orientation[2], orientation[3])

    def _读取向量(self, value: Any, expected_len: int) -> tuple[float, ...] | None:
        if not isinstance(value, list) or len(value) < expected_len:
            return None
        numbers: list[float] = []
        try:
            for item in value[:expected_len]:
                numbers.append(float(item))
        except (TypeError, ValueError):
            return None
        return tuple(numbers)

    def _限幅(self, value: float, limit: float) -> float:
        return max(-abs(limit), min(abs(limit), value))

    def _发布桥接状态(self) -> None:
        current_time = time.time()
        payload = {
            "motion_control_enabled": self._enable_motion_control,
            "sdk_ready": self._SDK实例 is not None,
            "telemetry_online": self._遥测在线,
            "telemetry_motion_ready": self._遥测可用(current_time),
            "telemetry_last_success_age_sec": self._计算时间差(current_time, self._最近遥测成功时间),
            "command_age_sec": self._计算时间差(current_time, self._最近速度命令.时间戳),
            "emergency_stop": self._当前急停,
            "arbitration_reason": self._当前速度裁决原因,
            "target_velocity": self._导出速度字典(self._当前裁决目标速度),
            "output_velocity": self._导出速度字典(self._当前输出速度),
        }
        message = String()
        message.data = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._bridge_status_publisher.publish(message)
        self._回灌桥接状态(payload)

    def _回灌桥接状态(self, payload: dict[str, Any]) -> None:
        if not self._回灌桥接状态到服务端 or self._遥测回灌套接字 is None:
            return

        try:
            message = json.dumps(
                {
                    "type": "bridge_status",
                    **payload,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self._遥测回灌套接字.sendto(message, (self._遥测UDP主机, self._遥测UDP端口))
        except Exception as exc:
            self._节流警告("control", f"回灌桥接状态到 robot-server 失败: {exc}")

    def _裁决目标速度(self, current_time: float) -> tuple[tuple[float, float, float], str]:
        if self._当前急停:
            return ((0.0, 0.0, 0.0), "emergency_stop")

        if current_time - self._最近速度命令.时间戳 > self._command_timeout_sec:
            return ((0.0, 0.0, 0.0), "command_timeout")

        if not self._遥测可用(current_time):
            return ((0.0, 0.0, 0.0), "telemetry_offline")

        return (self._应用原地转向策略(self._最近速度命令.导出元组()), "normal")

    def _遥测可用(self, current_time: float) -> bool:
        if not self._遥测离线时停止运动:
            return True
        if not self._遥测在线:
            return False
        if self._最近遥测成功时间 <= 0.0:
            return False
        return current_time - self._最近遥测成功时间 <= self._遥测离线超时秒数

    def _应用原地转向策略(self, target: tuple[float, float, float]) -> tuple[float, float, float]:
        if not self._启用原地转向:
            return target

        vx, vy, wz = target
        if abs(wz) < self._原地转向角速度阈值:
            return target
        if max(abs(vx), abs(vy)) > self._原地转向线速度死区:
            return target
        return (0.0, 0.0, wz)

    def _应用加速度限幅(
        self,
        target: tuple[float, float, float],
        current: tuple[float, float, float],
        delta_time: float,
    ) -> tuple[float, float, float]:
        return (
            self._按最大增量逼近(current[0], target[0], self._最大加速度x * delta_time),
            self._按最大增量逼近(current[1], target[1], self._最大加速度y * delta_time),
            self._按最大增量逼近(current[2], target[2], self._最大加速度z * delta_time),
        )

    def _按最大增量逼近(self, current: float, target: float, max_delta: float) -> float:
        if max_delta <= 0.0:
            return target

        delta = target - current
        if abs(delta) <= max_delta:
            return target
        if delta > 0.0:
            return current + max_delta
        return current - max_delta

    def _计算控制步长(self, current_time: float) -> float:
        delta = current_time - self._上次控制周期时间
        self._上次控制周期时间 = current_time
        if delta <= 0.0:
            return self._控制周期秒数
        return min(delta, 1.0)

    def _速度近似相等(
        self,
        left: tuple[float, float, float],
        right: tuple[float, float, float],
        tolerance: float = 1e-4,
    ) -> bool:
        return (
            abs(left[0] - right[0]) <= tolerance
            and abs(left[1] - right[1]) <= tolerance
            and abs(left[2] - right[2]) <= tolerance
        )

    def _导出速度字典(self, velocity: tuple[float, float, float]) -> dict[str, float]:
        return {
            "vx": velocity[0],
            "vy": velocity[1],
            "wz": velocity[2],
        }

    def _计算时间差(self, current_time: float, timestamp: float) -> float | None:
        if timestamp <= 0.0:
            return None
        return round(max(0.0, current_time - timestamp), 3)

    def _记录控制裁决(self, reason: str) -> None:
        if reason == self._上次控制裁决原因:
            return

        self._上次控制裁决原因 = reason
        if reason == "normal":
            self.get_logger().info("机器狗速度输出已恢复")
            return
        if reason == "emergency_stop":
            self.get_logger().warning("急停激活，持续输出零速度")
            return
        if reason == "telemetry_offline":
            self.get_logger().warning("遥测离线或超时，已暂停速度输出")
            return
        if reason == "motion_control_disabled":
            self.get_logger().info("运动控制已禁用，仅发布桥接状态和遥测")
            return
        if reason == "sdk_unavailable":
            self.get_logger().warning("机器狗 SDK 不可用，当前不会下发速度命令")
            return
        if reason == "control_error":
            self.get_logger().warning("速度下发失败，请检查 SDK 与网络链路")
            return
        self.get_logger().info("等待新的速度指令，当前输出零速度")

    def _节流警告(self, category: str, message: str) -> None:
        current_time = time.time()
        if category == "telemetry":
            if current_time - self._上次遥测错误日志时间 < 5.0:
                return
            self._上次遥测错误日志时间 = current_time
        else:
            if current_time - self._上次控制错误日志时间 < 5.0:
                return
            self._上次控制错误日志时间 = current_time
        self.get_logger().warning(message)

    def _读取字符串参数(self, key: str, fallback: str) -> str:
        value: Any = self.get_parameter(key).value
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    def _读取浮点参数(self, key: str, fallback: float) -> float:
        value: Any = self.get_parameter(key).value
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _读取整数参数(self, key: str, fallback: int) -> int:
        value: Any = self.get_parameter(key).value
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _读取布尔参数(self, key: str, fallback: bool) -> bool:
        value: Any = self.get_parameter(key).value
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        if value is None:
            return fallback
        return bool(value)

    def destroy_node(self) -> bool:
        """退出前确保速度归零。"""
        self._取消当前动作("node_shutdown")
        if self._SDK实例 is not None:
            try:
                self._SDK实例.move(0.0, 0.0, 0.0)
            except Exception:
                pass
        if self._遥测回灌套接字 is not None:
            try:
                self._遥测回灌套接字.close()
            except OSError:
                pass
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    """节点入口。"""
    rclpy.init(args=args)
    node = 机器狗桥接节点()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
