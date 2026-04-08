import json
import math
import threading
import time
from collections import deque
from typing import Any, Callable, Optional, Protocol

from sparkrobot_common import get_logger

from src.modules.vision import 从参数解析目标框, 打开视频流, 读取最新视频帧, 静态目标跟踪器

logger = get_logger("robot-agent")

动作执行函数 = Callable[[str, dict[str, Any]], bool]


class 动作客户端协议(Protocol):
    交互式子进程控制器: Any
    动作执行器: Optional[动作执行函数]
    动作控制器: Optional[Any]


# 姿态动作 → 控制参数映射（对应 TrickRobotDog 的姿态方法）
# TODO: 这个映射是为了兼容前端动作命名和后端执行器方法命名不一致的情况，后续可以逐步统一命名后移除
_ATTITUDE_ACTION_MAP: dict[str, dict[str, float]] = {
    "lean_left": {"roll_rate": -0.59},
    "lean_right": {"roll_rate": 0.59},
    "nod_up": {"pitch_rate": -0.59},
    "nod_down": {"pitch_rate": 0.59},
    "rotate_clockwise": {"yaw_rate": -0.59},
    "rotate_counterclockwise": {"yaw_rate": 0.59},
    "max_height": {"height_vel": 0.3},
    "min_height": {"height_vel": -0.3},
    "attitude_rest": {},
}

# 前端动作名 → executor ACTION_HANDLERS 键名映射
# TODO: 这个映射是为了兼容前端动作命名和后端执行器方法命名不一致的情况，后续可以逐步统一命名后移除
_ACTION_NAME_REMAP: dict[str, str] = {
    "lie_down": "sit_down"
}


class 动作调度器:
    def __init__(self, client: 动作客户端协议) -> None:
        self.client = client
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._closed = False
        self._strict_queue: deque[tuple[str, dict[str, Any]]] = deque()
        self._latest_pending: Optional[tuple[str, dict[str, Any], str]] = None
        self._running_policy: Optional[str] = None
        self._worker = threading.Thread(target=self._运行循环, daemon=True, name="robot-action-dispatcher")
        self._worker.start()

    def _分类策略(self, action: str) -> str:
        if action in {
            "estop", "sdk_mode", "camera_capture", "stand_up", "sit_down", "jump", "front_jump", "back_flip",
        }:
            return "strict_serial"
        if action in {
            "move", "move_by_distance", "turn_around", "lean_left", "lean_right", "nod_up",
            "nod_down", "rotate_clockwise", "rotate_counterclockwise", "max_height",
            "min_height", "attitude_rest", "approach_target", "vision_approach_target",
        }:
            return "preempt"
        return "latest_wins"

    def 提交(self, action: str, parameters: dict[str, Any]) -> bool:
        if not action:
            return False
        policy = self._分类策略(action)
        with self._lock:
            if self._closed:
                return False
            if policy == "strict_serial":
                self._strict_queue.append((action, parameters))
            else:
                self._latest_pending = (action, parameters, policy)
                if policy == "preempt" and self.client.动作控制器:
                    self.client.动作控制器.请求中断()
            self._wakeup.set()
        return True

    def 清空并中断(self) -> None:
        with self._lock:
            self._strict_queue.clear()
            self._latest_pending = None
            self._wakeup.set()
        if self.client.动作控制器:
            self.client.动作控制器.请求中断()

    def 关闭(self) -> None:
        with self._lock:
            self._closed = True
            self._strict_queue.clear()
            self._latest_pending = None
            self._wakeup.set()
        if self.client.动作控制器:
            self.client.动作控制器.请求中断()
        self._worker.join(timeout=2.0)

    def _取下一个命令(self) -> Optional[tuple[str, dict[str, Any], str]]:
        with self._lock:
            if self._strict_queue:
                action, parameters = self._strict_queue.popleft()
                self._running_policy = "strict_serial"
                return (action, parameters, "strict_serial")
            if self._latest_pending:
                cmd = self._latest_pending
                self._latest_pending = None
                self._running_policy = cmd[2]
                return cmd
            self._running_policy = None
            return None

    def _运行循环(self) -> None:
        while True:
            cmd = self._取下一个命令()
            if cmd is None:
                with self._lock:
                    if self._closed:
                        return
                self._wakeup.wait(timeout=0.5)
                self._wakeup.clear()
                continue
            action, parameters, policy = cmd
            try:
                executor = self.client.动作执行器
                if not executor:
                    logger.warning(f"未设置动作执行器，跳过动作: {action}")
                    continue
                result = executor(action, parameters)
                logger.debug(f"动作调度执行完成: action={action}, policy={policy}, result={result}")
            except Exception as e:
                logger.error(f"动作调度执行失败: action={action}, policy={policy}, error={e}", exc_info=True)


class 动作执行器:
    def __init__(self, client: 动作客户端协议) -> None:
        self.client = client
        self._current_token = 0
        self._token_lock = threading.Lock()

    def _读取当前_token(self) -> int:
        with self._token_lock:
            return self._current_token

    def _下一个_token(self) -> int:
        """生成下一个令牌"""
        with self._token_lock:
            self._current_token += 1
            return self._current_token

    def 请求中断(self) -> None:
        self._下一个_token()
        try:
            self.client.交互式子进程控制器.发送命令(json.dumps({"type": "cancel_action"}))
        except Exception:
            pass
        self._停止当前动作()

    def _停止当前动作(self) -> None:
        """停止当前动作"""
        try:
            self._发送停止移动命令()
            self.client.交互式子进程控制器.发送命令(
                json.dumps({
                    "type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0
                })
            )
        except Exception:
            pass

    def _发送停止移动命令(self, duration: float = 0.0) -> None:
        """发送零速度命令，必要时使用 ai_move 覆盖正在执行的定时移动。"""
        stop_payload: dict[str, float | str] = {"vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}
        if duration > 0.0:
            stop_payload["type"] = "ai_move"
            stop_payload["duration"] = duration
        else:
            stop_payload["type"] = "move"
        self.client.交互式子进程控制器.发送命令(json.dumps(stop_payload))

    def _解析等待时间(self, action: str) -> float:
        """解析动作等待时间"""
        if action in ["walk_forward", "walk_backward", "turn_left", "turn_right"]:
            return 2.5
        if action in ["shake_hand", "nod"]:
            return 4.5
        if action == "dance":
            return 5.0
        return 3.5

    def _可中断的睡眠(self, token: int, seconds: float) -> bool:
        """可中断的睡眠"""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if token != self._读取当前_token():
                return False
            time.sleep(0.1)
        return True

    def _转换距离参数到速度(self, parameters: dict[str, Any]) -> tuple[float, float, float, float]:
        """
        将距离/步数/角度参数转换为速度和持续时间
        返回: (vx, vy, yaw_rate, duration)
        """
        vx = 0.0
        vy = 0.0
        yaw_rate = 0.0
        duration = 0.0

        # 默认速度配置（可从 config 读取）
        default_vx_speed = 0.2       # 前后移动速度 m/s
        default_vy_speed = 0.15      # 左右移动速度 m/s
        default_yaw_speed = 0.5      # 转向角速度 rad/s
        default_step_distance = 0.3  # 每步距离 m（其实多了，但是更符合直觉，于是保留）
        default_move_speed = 0.2     # 斜向移动的默认速度 m/s

        # 处理步数移动，先转换为距离
        if "steps" in parameters:
            steps = float(parameters["steps"])
            distance = steps * default_step_distance
            parameters["distance"] = distance

        # 情况1: angle + distance/steps，斜向移动
        if "angle" in parameters and "distance" in parameters:
            angle_deg = float(parameters["angle"])
            distance = float(parameters["distance"])
            angle_rad = angle_deg * math.pi / 180.0

            # angle=0 是正前方，angle=90 是左方，angle=-90 是右方
            vx = default_move_speed * math.cos(angle_rad)
            vy = default_move_speed * math.sin(angle_rad)
            duration = abs(distance) / default_move_speed

            logger.info(f"斜向移动: 角度={angle_deg}°, 距离={distance}m, vx={vx:.2f}, vy={vy:.2f}, 时长={duration:.2f}s")
            return (vx, vy, 0.0, duration)

        # 情况2: 只有 angle，原地转向
        if "angle" in parameters:
            angle_deg = float(parameters["angle"])
            angle_rad = abs(angle_deg * math.pi / 180.0)
            yaw_rate = default_yaw_speed if angle_deg > 0 else -default_yaw_speed
            duration = angle_rad / default_yaw_speed
            logger.info(f"原地转向: 角度={angle_deg}°, 时长={duration:.2f}s")
            return (0.0, 0.0, yaw_rate, duration)

        # 情况3: distance + direction，指定方向移动
        if "distance" in parameters:
            distance = float(parameters["distance"])
            direction = parameters.get("direction", "forward")

            if direction == "forward":
                vx = default_vx_speed
                duration = abs(distance) / default_vx_speed
            elif direction == "backward":
                vx = -default_vx_speed
                duration = abs(distance) / default_vx_speed
            elif direction == "left":
                vy = default_vy_speed
                duration = abs(distance) / default_vy_speed
            elif direction == "right":
                vy = -default_vy_speed
                duration = abs(distance) / default_vy_speed
            else:
                vx = default_vx_speed if distance > 0 else -default_vx_speed
                duration = abs(distance) / default_vx_speed

            logger.info(f"方向移动: {direction}, 距离={distance}m, 时长={duration:.2f}s")

        return (vx, vy, yaw_rate, duration)

    def _执行目标靠近(self, token: int, parameters: dict[str, Any]) -> bool:
        cx = float(parameters.get("cx", 0.5))
        w = float(parameters.get("w", 0.12))
        stop_area = float(parameters.get("stop_area", 0.22))
        max_seconds = float(parameters.get("max_seconds", 6.0))
        heading_gain = float(parameters.get("heading_gain", 2.4))
        max_yaw_rate = float(parameters.get("max_yaw_rate", 0.8))
        min_vx = float(parameters.get("min_vx", 0.08))
        max_vx = float(parameters.get("max_vx", 0.18))
        min_vx = max(0.03, min(min_vx, 0.25))
        max_vx = max(min_vx, min(max_vx, 0.28))
        heading_gain = max(0.4, min(heading_gain, 4.2))
        max_yaw_rate = max(0.3, min(max_yaw_rate, 1.2))
        stop_area = max(0.03, min(stop_area, 0.8))
        max_seconds = max(0.5, min(max_seconds, 8.0))
        h = float(parameters.get("h", w))
        h = max(0.0, min(1.0, h))
        area = max(0.0, min(1.0, w * h))
        cx = max(0.0, min(1.0, cx))
        center_error = max(-1.0, min(1.0, cx - 0.5))
        if area >= stop_area:
            self._发送停止移动命令(0.1)
            return True
        normalized_gap = max(0.0, (stop_area - area) / stop_area)
        vx = min_vx + (max_vx - min_vx) * normalized_gap
        # 目标在画面右侧时，应向右转让目标回到中心；此前符号相反会越转越偏。
        yaw_rate = max(-max_yaw_rate, min(max_yaw_rate, heading_gain * center_error))
        rotate_duration = max(0.25, min(1.8, abs(center_error) * 2.6))
        move_duration = max(0.4, min(max_seconds, 0.8 + normalized_gap * 2.2))
        if abs(yaw_rate) >= 0.05:
            rotate_command = json.dumps({
                "type": "ai_move",
                "vx": 0.0,
                "vy": 0.0,
                "yaw_rate": round(yaw_rate, 4),
                "duration": round(rotate_duration, 4),
            })
            success = self.client.交互式子进程控制器.发送命令(rotate_command)
            if not success:
                return False
            if not self._可中断的睡眠(token, rotate_duration):
                return False
        move_command = json.dumps({
            "type": "ai_move",
            "vx": round(vx, 4),
            "vy": 0.0,
            "yaw_rate": 0.0,
            "duration": round(move_duration, 4),
        })
        success = self.client.交互式子进程控制器.发送命令(move_command)
        if not success:
            return False
        if not self._可中断的睡眠(token, move_duration):
            return False
        self._发送停止移动命令(0.2)
        return True

    def _执行视觉目标靠近(self, token: int, parameters: dict[str, Any]) -> bool:
        rtsp_url = str(parameters.get("rtsp_url", "rtsp://127.0.0.1:8554/test"))
        timeout = max(1, min(int(parameters.get("timeout", 5)), 15))
        warmup_reads = max(1, min(int(parameters.get("warmup_reads", 3)), 10))
        max_track_seconds = max(2.0, min(float(parameters.get("max_track_seconds", 18.0)), 60.0))
        max_lost_frames = max(1, min(int(parameters.get("max_lost_frames", 4)), 20))
        min_score = max(-1.0, min(float(parameters.get("min_score", 0.18)), 1.0))
        search_margin = max(1.1, min(float(parameters.get("search_margin", 1.8)), 3.5))
        template_update_rate = max(0.0, min(float(parameters.get("template_update_rate", 0.2)), 1.0))
        cx_offset = max(-0.25, min(float(parameters.get("cx_offset", 0.0)), 0.25))
        cy_offset = max(-0.25, min(float(parameters.get("cy_offset", 0.0)), 0.25))

        bbox = 从参数解析目标框(parameters)
        tracker = 静态目标跟踪器(
            initial_bbox=bbox,
            search_margin=search_margin,
            min_score=min_score,
            template_update_rate=template_update_rate,
        )

        cap = None
        try:
            cap = 打开视频流(rtsp_url, timeout)
            if not cap.isOpened():
                logger.error(f"无法打开 RTSP 流: {rtsp_url}")
                return False

            first_frame = 读取最新视频帧(cap, warmup_reads=warmup_reads)
            if first_frame is None:
                logger.error("无法从 RTSP 流读取首帧")
                return False

            initial_bbox = tracker.初始化(first_frame)
            logger.info(
                "视觉靠近启动: "
                f"rtsp={rtsp_url}, 初始框=(cx={initial_bbox.cx:.3f}, cy={initial_bbox.cy:.3f}, "
                f"w={initial_bbox.w:.3f}, h={initial_bbox.h:.3f})"
            )

            start_time = time.time()
            lost_frames = 0
            control_parameters = dict(parameters)
            control_parameters.setdefault("max_seconds", 1.2)
            control_parameters.setdefault("min_vx", 0.08)
            control_parameters.setdefault("max_vx", 0.16)
            control_parameters.setdefault("heading_gain", 2.0)
            control_parameters.setdefault("max_yaw_rate", 0.6)

            while time.time() - start_time < max_track_seconds:
                if token != self._读取当前_token():
                    self._发送停止移动命令(0.2)
                    return False

                frame = 读取最新视频帧(cap, warmup_reads=1)
                if frame is None:
                    lost_frames += 1
                    logger.warning(f"视觉靠近读取视频帧失败: lost_frames={lost_frames}/{max_lost_frames}")
                    if lost_frames >= max_lost_frames:
                        break
                    continue

                tracked = tracker.更新(frame)
                if tracked is None:
                    lost_frames += 1
                    logger.warning(f"视觉靠近跟踪丢失: lost_frames={lost_frames}/{max_lost_frames}")
                    if lost_frames >= max_lost_frames:
                        break
                    continue

                lost_frames = 0
                tracked_bbox, score = tracked
                control_parameters["cx"] = max(0.0, min(1.0, tracked_bbox.cx + cx_offset))
                control_parameters["cy"] = max(0.0, min(1.0, tracked_bbox.cy + cy_offset))
                control_parameters["w"] = tracked_bbox.w
                control_parameters["h"] = tracked_bbox.h

                logger.info(
                    "视觉靠近跟踪: "
                    f"score={score:.3f}, cx={control_parameters['cx']:.3f}, cy={control_parameters['cy']:.3f}, "
                    f"w={tracked_bbox.w:.3f}, h={tracked_bbox.h:.3f}, area={tracked_bbox.area:.3f}"
                )

                if not self._执行目标靠近(token, control_parameters):
                    return False

                stop_area = float(control_parameters.get("stop_area", 0.22))
                stop_height = float(control_parameters.get("stop_height", 0.0))
                if tracked_bbox.area >= stop_area or (stop_height > 0.0 and tracked_bbox.h >= stop_height):
                    logger.info("视觉靠近完成，已满足停止阈值")
                    return True

            logger.warning("视觉靠近结束：跟踪超时或连续丢失目标")
            self._发送停止移动命令(0.2)
            return False
        except Exception as e:
            logger.error(f"执行视觉目标靠近失败: {e}", exc_info=True)
            self._发送停止移动命令(0.2)
            return False
        finally:
            if cap is not None:
                cap.release()

    def _执行自定义动作(self, action: str, token: int, parameters: dict[str, Any]) -> Optional[bool]:
        if action == "approach_target":
            result = self._执行目标靠近(token, parameters)
            logger.info(f"目标靠近执行结果: {result}, 参数: {parameters}")
            return result
        if action == "vision_approach_target":
            result = self._执行视觉目标靠近(token, parameters)
            logger.info(f"视觉目标靠近执行结果: {result}, 参数: {parameters}")
            return result
        return None

    def 执行动作(self, action: str, parameters: dict[str, Any]) -> bool:
        """执行动作（操作机器人行动的动作）"""
        try:
            token = self._下一个_token()
            command: Optional[str] = None
            wait_time = 0.0

            logger.debug(f"开始执行动作: {action}, 参数: {parameters}")
            self._停止当前动作()
            custom_result = self._执行自定义动作(action, token, parameters)
            if custom_result is not None:
                return custom_result

            # 特殊处理 move 动作
            if action == "move":
                if "distance" in parameters or "steps" in parameters or "angle" in parameters:
                    vx, vy, yaw_rate, duration = self._转换距离参数到速度(parameters)
                    command = json.dumps({
                        "type": "ai_move",
                        "vx": vx,
                        "vy": vy,
                        "yaw_rate": yaw_rate,
                        "duration": duration,
                    })
                    wait_time = duration
                    logger.info(f"移动控制（距离模式）: vx={vx:.2f}, vy={vy:.2f}, yaw_rate={yaw_rate:.2f}, duration={duration:.2f}秒")
                else:
                    vx = parameters.get("vx", 0)
                    vy = parameters.get("vy", 0)
                    yaw_rate = parameters.get("yaw_rate", 0)
                    duration = parameters.get("duration", 2)
                    command = json.dumps({
                        "type": "ai_move",
                        "vx": vx,
                        "vy": vy,
                        "yaw_rate": yaw_rate,
                        "duration": duration,
                    })
                    wait_time = float(duration)
                    logger.info(f"移动控制（速度模式）: vx={vx}, vy={vy}, yaw_rate={yaw_rate}, duration={duration}秒")
            # TODO: 后续可以逐步废弃 move_by_distance 和 turn_around，统一使用 move + 参数的方式来控制移动和转向，让前端/手机端就换算好，而不是改机器狗本体来适配不同的控制方式
            elif action == "move_by_distance":
                axis = parameters.get("axis", "x")
                distance = float(parameters.get("distance", 1.0))
                speed = float(parameters.get("speed", 0.5))
                vx, vy = 0.0, 0.0
                if axis == "x":
                    vx = speed
                elif axis == "-x":
                    vx = -speed
                elif axis == "y":
                    vy = speed
                elif axis == "-y":
                    vy = -speed
                duration = abs(distance) / speed
                command = json.dumps({"type": "ai_move", "vx": vx, "vy": vy, "yaw_rate": 0.0, "duration": duration})
                wait_time = duration
                logger.info(f"按距离移动: axis={axis}, distance={distance}m, speed={speed}m/s, duration={duration:.2f}s")
            elif action == "turn_around":
                angle = float(parameters.get("angle", 180.0))
                speed_deg = float(parameters.get("speed", 30))
                direction = parameters.get("direction", "cw")
                angle_rad = angle * math.pi / 180.0
                yaw_rate_rad = round(speed_deg * math.pi / 180.0, 4)
                actual_yaw_rate = -yaw_rate_rad if direction == "cw" else yaw_rate_rad
                duration = round(abs(angle_rad) / abs(yaw_rate_rad), 4)
                command = json.dumps({"type": "ai_move", "vx": 0.0, "vy": 0.0, "yaw_rate": actual_yaw_rate, "duration": duration})
                wait_time = duration
                logger.info(f"原地转身: angle={angle}°, speed={speed_deg}°/s, direction={direction}, duration={duration:.2f}s")
            elif action in _ATTITUDE_ACTION_MAP:
                attitude_defaults = _ATTITUDE_ACTION_MAP[action]
                duration = float(parameters.get("duration", 0.5))
                reset = float(parameters.get("reset", 0))
                height_vel = attitude_defaults.get("height_vel", 0.0)
                if "_height_vel" in parameters:
                    height_vel = float(parameters["_height_vel"])
                command = json.dumps({
                    "type": "attitude",
                    "roll_rate": attitude_defaults.get("roll_rate", 0.0),
                    "pitch_rate": attitude_defaults.get("pitch_rate", 0.0),
                    "yaw_rate": attitude_defaults.get("yaw_rate", 0.0),
                    "height_vel": height_vel,
                })
                success = self.client.交互式子进程控制器.发送命令(command)
                if not success:
                    logger.error(f"发送姿态命令失败: {action}")
                    return False
                logger.info(f"姿态控制: {action}, duration={duration}s, reset={reset}s")
                if not self._可中断的睡眠(token, duration):
                    logger.info(f"姿态动作 {action} 被打断")
                    return False
                if reset > 0:
                    reset_cmd = json.dumps({"type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0})
                    self.client.交互式子进程控制器.发送命令(reset_cmd)
                    if not self._可中断的睡眠(token, reset):
                        logger.info(f"姿态复位 {action} 被打断")
                        return False
                logger.debug(f"姿态动作 {action} 执行完成")
                return True
            else:
                command = _ACTION_NAME_REMAP.get(action, action)
                wait_time = self._解析等待时间(action)

            if not command:
                logger.warning(f"不支持的动作: {action}")
                return False
            success = self.client.交互式子进程控制器.发送命令(command)
            if not success:
                logger.error(f"发送命令 {command} 失败")
                return False
            completed = self._可中断的睡眠(token, wait_time)
            if not completed:
                logger.info(f"动作 {action} 被打断")
                return False
            logger.debug(f"动作 {action} 执行完成")
            return True
        except Exception as e:
            logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False
