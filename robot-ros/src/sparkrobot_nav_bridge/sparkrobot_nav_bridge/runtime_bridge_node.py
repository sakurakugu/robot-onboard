from __future__ import annotations

import json
import math
import queue
import socketserver
import threading
import time
import uuid
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


@dataclass
class 桥接命令:
    """等待在 ROS 线程中执行的桥接命令。"""

    请求ID: str
    方法: str
    参数: dict[str, Any]
    响应Future: Future[dict[str, Any]]


class 导航桥Socket处理器(socketserver.StreamRequestHandler):
    """导航桥 Socket 请求处理器。"""

    def _获取桥接服务器(self) -> "导航桥Socket服务器":
        return cast("导航桥Socket服务器", self.server)

    def handle(self) -> None:
        while True:
            raw = self.rfile.readline()
            if not raw:
                return

            request_id = "unknown"
            try:
                message = json.loads(raw.decode("utf-8").strip())
                if not isinstance(message, dict):
                    raise ValueError("请求必须是 JSON 对象")

                request_id = str(message.get("id") or "unknown")
                if message.get("type") != "request":
                    server = self._获取桥接服务器()
                    response = server.节点.构建错误响应(request_id, "invalid_message_type", "仅支持 request 类型消息")
                    self.wfile.write(server.节点.编码消息(response))
                    self.wfile.flush()
                    continue

                method = str(message.get("method") or "").strip()
                params = message.get("params", {})
                if not isinstance(params, dict):
                    server = self._获取桥接服务器()
                    response = server.节点.构建错误响应(request_id, "invalid_params", "params 必须是对象")
                    self.wfile.write(server.节点.编码消息(response))
                    self.wfile.flush()
                    continue

                response_future: Future[dict[str, Any]] = Future()
                command = 桥接命令(
                    请求ID=request_id,
                    方法=method,
                    参数=params,
                    响应Future=response_future,
                )
                server = self._获取桥接服务器()
                server.节点.提交命令(command)
                response = response_future.result(timeout=30.0)
            except Exception as exc:
                server = self._获取桥接服务器()
                response = server.节点.构建错误响应(request_id, "internal_error", f"导航桥内部错误: {exc}")

            server = self._获取桥接服务器()
            self.wfile.write(server.节点.编码消息(response))
            self.wfile.flush()


导航桥Socket服务器基类: Any = getattr(socketserver, "ThreadingUnixStreamServer", socketserver.ThreadingTCPServer)


class 导航桥Socket服务器(导航桥Socket服务器基类):
    """带节点上下文的导航桥 Socket 服务器。"""

    daemon_threads = True

    def __init__(self, server_address: str, handler_class: type[导航桥Socket处理器], 节点: "运行时桥接节点") -> None:
        self.节点 = 节点
        super().__init__(server_address, handler_class)


class 运行时桥接节点(Node):
    """`robot-runtime <-> Nav2` 的本地桥接节点。"""

    def __init__(self) -> None:
        super().__init__("sparkrobot_runtime_bridge")
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("imu_topic", "/imu")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("scan_max_points", 720)
        self.declare_parameter("navigation_action_name", "navigate_to_pose")
        self.declare_parameter("socket_path", "/tmp/sparkrobot/ros-nav-bridge.sock")
        self.declare_parameter("action_server_wait_sec", 10.0)

        self._command_queue: queue.Queue[桥接命令] = queue.Queue()
        self._socket_server: 导航桥Socket服务器 | None = None
        self._socket_thread: threading.Thread | None = None
        self._socket_path = Path(self._读取字符串参数("socket_path", "/tmp/sparkrobot/ros-nav-bridge.sock"))
        self._action_client = ActionClient(
            self,
            NavigateToPose,
            self._读取字符串参数("navigation_action_name", "navigate_to_pose"),
        )

        self._goal_request_inflight = False
        self._goal_handle: Any | None = None
        self._goal_result_future: Any | None = None
        self._current_state = "idle"
        self._current_goal: dict[str, Any] | None = None
        self._remaining_distance: float | None = None
        self._failure_reason: str | None = None
        self._last_result: dict[str, Any] | None = None
        self._scan_max_points = self._读取整数参数("scan_max_points", 720)
        self._latest_scan: dict[str, Any] = self._构建空激光扫描()
        self._scan_subscription = self.create_subscription(
            LaserScan,
            self._读取字符串参数("scan_topic", "/scan"),
            self._处理激光扫描,
            10,
        )

        self._启动socket服务()
        self._command_timer = self.create_timer(0.1, self._处理命令队列)
        self._status_timer = self.create_timer(10.0, self._输出状态)
        self.get_logger().info(f"运行时桥接节点已启动，socket={self._socket_path}")

    def 提交命令(self, command: 桥接命令) -> None:
        """提交待执行命令。"""
        self._command_queue.put(command)

    def 构建成功响应(self, request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """构建成功响应。"""
        return {
            "type": "response",
            "id": request_id,
            "success": True,
            "result": result,
        }

    def 构建错误响应(
        self,
        request_id: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建错误响应。"""
        return {
            "type": "response",
            "id": request_id,
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        }

    def 编码消息(self, message: dict[str, Any]) -> bytes:
        """编码为 JSON Line。"""
        return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    def _处理命令队列(self) -> None:
        while True:
            try:
                command = self._command_queue.get_nowait()
            except queue.Empty:
                return
            self._处理单个命令(command)

    def _处理单个命令(self, command: 桥接命令) -> None:
        if command.方法 == "bridge.ping":
            self._设置响应结果(
                command,
                self.构建成功响应(
                    command.请求ID,
                    {
                        "ok": True,
                        "socket_path": str(self._socket_path),
                        "status": self._构建导航状态摘要(),
                    },
                ),
            )
            return

        if command.方法 == "navigation.get_status":
            self._设置响应结果(command, self.构建成功响应(command.请求ID, self._构建导航状态摘要()))
            return

        if command.方法 == "lidar.get_scan":
            self._设置响应结果(command, self.构建成功响应(command.请求ID, dict(self._latest_scan)))
            return

        if command.方法 == "navigation.navigate_to":
            self._执行导航到目标(command)
            return

        if command.方法 == "navigation.cancel":
            self._执行取消导航(command)
            return

        self._设置响应结果(
            command,
            self.构建错误响应(command.请求ID, "method_not_found", f"未支持的方法: {command.方法}"),
        )

    def _执行导航到目标(self, command: 桥接命令) -> None:
        if self._goal_request_inflight:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_dispatch_in_progress", "当前已有目标正在发送中"),
            )
            return

        if self._current_state in {"pending", "running"} and self._goal_handle is not None:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_active", "当前已有导航目标正在执行"),
            )
            return

        try:
            goal = self._解析目标参数(command.参数)
        except ValueError as exc:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "invalid_goal", str(exc)),
            )
            return

        if not self._action_client.wait_for_server(timeout_sec=self._读取浮点参数("action_server_wait_sec", 10.0)):
            self._设置响应结果(
                command,
                self.构建错误响应(
                    command.请求ID,
                    "nav_action_unavailable",
                    "Nav2 navigate_to_pose Action 未就绪",
                ),
            )
            return

        self._goal_request_inflight = True
        self._current_goal = goal
        self._current_state = "pending"
        self._remaining_distance = None
        self._failure_reason = None
        self._last_result = None

        goal_msg = self._构建导航消息(goal)
        send_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self._导航反馈回调)
        send_future.add_done_callback(lambda future, command=command, goal=goal: self._导航目标响应回调(future, command, goal))

    def _执行取消导航(self, command: 桥接命令) -> None:
        if self._goal_request_inflight:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_dispatch_in_progress", "导航目标仍在发送中，暂时不能取消"),
            )
            return

        if self._goal_handle is None:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_not_active", "当前没有可取消的导航目标"),
            )
            return

        cancel_future = self._goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(lambda future, command=command: self._导航取消响应回调(future, command))

    def _导航目标响应回调(self, future: Any, command: 桥接命令, goal: dict[str, Any]) -> None:
        self._goal_request_inflight = False
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._current_state = "failed"
            self._failure_reason = f"发送导航目标失败: {exc}"
            self._set_terminal_result("failed", self._failure_reason)
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_send_failed", self._failure_reason, self._构建导航状态摘要()),
            )
            return

        if not goal_handle.accepted:
            self._current_state = "failed"
            self._failure_reason = "Nav2 拒绝了该导航目标"
            self._goal_handle = None
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_rejected", self._failure_reason, self._构建导航状态摘要()),
            )
            return

        self._goal_handle = goal_handle
        self._current_goal = goal
        self._current_state = "running"
        self._failure_reason = None
        self._goal_result_future = goal_handle.get_result_async()
        self._goal_result_future.add_done_callback(self._导航结果回调)
        self._设置响应结果(
            command,
            self.构建成功响应(
                command.请求ID,
                {
                    "accepted": True,
                    "status": self._构建导航状态摘要(),
                },
            ),
        )

    def _导航取消响应回调(self, future: Any, command: 桥接命令) -> None:
        try:
            cancel_response = future.result()
        except Exception as exc:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_cancel_failed", f"取消导航目标失败: {exc}"),
            )
            return

        goals_canceling = list(getattr(cancel_response, "goals_canceling", []))
        if not goals_canceling:
            self._设置响应结果(
                command,
                self.构建错误响应(command.请求ID, "goal_cancel_rejected", "Nav2 没有接受取消请求"),
            )
            return

        self._current_state = "cancelled"
        self._remaining_distance = None
        self._failure_reason = None
        self._设置响应结果(
            command,
            self.构建成功响应(
                command.请求ID,
                {
                    "cancelled": True,
                    "status": self._构建导航状态摘要(),
                },
            ),
        )

    def _导航反馈回调(self, feedback_msg: Any) -> None:
        feedback = getattr(feedback_msg, "feedback", None)
        if feedback is None:
            return
        distance_remaining = getattr(feedback, "distance_remaining", None)
        if distance_remaining is not None:
            try:
                self._remaining_distance = float(distance_remaining)
            except (TypeError, ValueError):
                self._remaining_distance = None
        if self._current_state not in {"succeeded", "cancelled", "failed"}:
            self._current_state = "running"

    def _导航结果回调(self, future: Any) -> None:
        try:
            result_wrapper = future.result()
        except Exception as exc:
            self._set_terminal_result("failed", f"获取导航结果失败: {exc}")
            return

        status = int(getattr(result_wrapper, "status", GoalStatus.STATUS_UNKNOWN))
        result = getattr(result_wrapper, "result", None)
        self._last_result = {
            "status_code": status,
            "error_code": getattr(result, "error_code", None),
            "error_msg": getattr(result, "error_msg", None),
        }

        if status == GoalStatus.STATUS_SUCCEEDED:
            self._current_state = "succeeded"
            self._remaining_distance = 0.0
            self._failure_reason = None
        elif status == GoalStatus.STATUS_CANCELED:
            self._current_state = "cancelled"
            self._remaining_distance = None
            self._failure_reason = None
        else:
            self._current_state = "failed"
            self._remaining_distance = None
            self._failure_reason = self._提取失败原因(status, result)

        self._goal_handle = None
        self._goal_result_future = None

    def _set_terminal_result(self, state: str, failure_reason: str | None) -> None:
        self._current_state = state
        self._goal_handle = None
        self._goal_result_future = None
        self._remaining_distance = None
        self._failure_reason = failure_reason

    def _提取失败原因(self, status_code: int, result: Any) -> str:
        error_msg = getattr(result, "error_msg", None)
        if error_msg:
            return str(error_msg)
        error_code = getattr(result, "error_code", None)
        if error_code is not None:
            return f"导航失败，status={status_code}，error_code={error_code}"
        return f"导航失败，status={status_code}"

    def _构建导航状态摘要(self) -> dict[str, Any]:
        return {
            "state": self._current_state,
            "current_goal": self._current_goal,
            "remaining_distance": self._remaining_distance,
            "failure_reason": self._failure_reason,
            "last_result": self._last_result,
            "action_server_ready": bool(self._action_client.server_is_ready()),
        }

    def _构建空激光扫描(self) -> dict[str, Any]:
        return {
            "available": False,
            "frame_id": self._读取字符串参数("scan_topic", "/scan"),
            "angle_min": 0.0,
            "angle_max": 0.0,
            "angle_increment": 0.0,
            "range_min": 0.0,
            "range_max": 0.0,
            "scan_time": None,
            "time_increment": None,
            "ranges": [],
            "point_count": 0,
            "captured_at": 0,
        }

    def _处理激光扫描(self, message: LaserScan) -> None:
        ranges = [self._归一化量测值(item) for item in message.ranges]
        sampled_ranges, actual_step = self._压缩激光扫描(ranges)
        angle_increment = float(message.angle_increment) * actual_step
        angle_min = float(message.angle_min)
        angle_max = angle_min + angle_increment * max(len(sampled_ranges) - 1, 0)
        point_count = sum(1 for item in sampled_ranges if item is not None)

        self._latest_scan = {
            "available": True,
            "frame_id": message.header.frame_id or "laser",
            "angle_min": angle_min,
            "angle_max": angle_max,
            "angle_increment": angle_increment,
            "range_min": float(message.range_min),
            "range_max": float(message.range_max),
            "scan_time": float(message.scan_time) if math.isfinite(float(message.scan_time)) else None,
            "time_increment": float(message.time_increment) if math.isfinite(float(message.time_increment)) else None,
            "ranges": sampled_ranges,
            "point_count": point_count,
            "captured_at": int(time.time() * 1000),
        }

    def _压缩激光扫描(self, ranges: list[float | None]) -> tuple[list[float | None], int]:
        if len(ranges) <= self._scan_max_points:
            return ranges, 1

        step = max(1, math.ceil(len(ranges) / self._scan_max_points))
        return ranges[::step], step

    def _归一化量测值(self, value: float) -> float | None:
        number = float(value)
        if not math.isfinite(number):
            return None
        return number

    def _构建导航消息(self, goal: dict[str, Any]) -> NavigateToPose.Goal:
        message = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = str(goal.get("frame_id") or "map")
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(goal["x"])
        pose.pose.position.y = float(goal["y"])
        pose.pose.position.z = 0.0

        yaw = float(goal["yaw"])
        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        message.pose = pose
        return message

    def _解析目标参数(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            x = float(params["x"])
            y = float(params["y"])
            yaw = float(params["yaw"])
        except KeyError as exc:
            raise ValueError(f"缺少必要参数: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"导航目标参数格式错误: {exc}") from exc

        frame_id = str(params.get("frame_id") or "map").strip() or "map"
        goal_id = str(params.get("id") or params.get("goal_id") or uuid.uuid4()).strip()
        map_name = str(params.get("map_name") or "").strip()
        return {
            "id": goal_id,
            "map_name": map_name or None,
            "frame_id": frame_id,
            "x": x,
            "y": y,
            "yaw": yaw,
        }

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

    def _设置响应结果(self, command: 桥接命令, response: dict[str, Any]) -> None:
        if not command.响应Future.done():
            command.响应Future.set_result(response)

    def _输出状态(self) -> None:
        status = self._构建导航状态摘要()
        self.get_logger().info(
            "导航桥心跳: "
            f"state={status['state']}, "
            f"goal={status['current_goal']}, "
            f"remaining_distance={status['remaining_distance']}, "
            f"action_ready={status['action_server_ready']}"
        )

    def _启动socket服务(self) -> None:
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._socket_server = 导航桥Socket服务器(str(self._socket_path), 导航桥Socket处理器, self)
        self._socket_thread = threading.Thread(target=self._socket_server.serve_forever, daemon=True)
        self._socket_thread.start()

    def _关闭socket服务(self) -> None:
        if self._socket_server is not None:
            self._socket_server.shutdown()
            self._socket_server.server_close()
            self._socket_server = None

        if self._socket_thread is not None:
            self._socket_thread.join(timeout=1.0)
            self._socket_thread = None

        try:
            if self._socket_path.exists():
                self._socket_path.unlink()
        except OSError as exc:
            self.get_logger().warning(f"清理导航桥 Socket 失败: {exc}")

    def destroy_node(self) -> bool:
        """销毁节点前先关闭本地 Socket。"""
        self._关闭socket服务()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    """节点入口。"""
    rclpy.init(args=args)
    node = 运行时桥接节点()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
