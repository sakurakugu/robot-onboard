# from .core import RobotDog
# from .crazy import CrazyRobotDog
# from .utils import execute_concurrently
# from .logger import logger

# __all__ = [
#     "RobotDog",
#     "CrazyRobotDog",
#     "execute_concurrently",
#     "logger",
# ]

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Literal
import time
import math
import sys
from pathlib import Path
import socket
import platform
import re

# 根据平台和架构选择对应的静态库的路径
machine = platform.machine().lower()
arch = "aarch64" if ("aarch64" in machine or "arm64" in machine) else "x86_64"
so_dir = Path(__file__).parent.parent / "so" / arch
sys.path.insert(0, str(so_dir))

try:
    import mc_sdk_zsl_1_py
except ImportError as e:
    raise ImportError(f"无法导入 mc_sdk_zsl_1_py，请检查 {so_dir} 下是否存在 .so 文件") from e


# 导出所需的类和函数
__all__ = [
    "RobotDog",
    "CrazyRobotDog",
    "execute_concurrently"
]


tz = timezone(timedelta(hours=8))
def log(flag: str, name: str, action: str, result: str):
    """日志记录

    Args:
        flag (str): 成功或失败标识
        name (str): 机器狗名称
        action (str): 动作名称
        result (str): 结果描述
    """
    # 记录当前时间，格式为ISO 8601(始终包含+-而不用Z)，并且精确到微秒
    timestamp = datetime.now(tz).isoformat(timespec='microseconds') 
    print(
        f"[{timestamp}] [{flag}] [{name}] {action} -> {result}"
    )


def execute_concurrently(*actions, _interval: float = 0):
    """并发执行不同机器狗的动作"""
    with ThreadPoolExecutor() as executor:
        futures = []
        for action in actions:
            futures.append(executor.submit(action)) # 提交动作到线程池
            time.sleep(_interval)                   # 微小延时，避免瞬时大量请求导致网络拥堵
        for future in futures:
            future.result()                         # 等待动作完成


def get_local_ip():
    """通过UDP连接获取本机对外的IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的建立连接，仅用于获取本机出口IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        # 增加异常处理，避免网络问题导致程序崩溃
        print(f"获取出口IP失败: {e}")
        ip = None
    finally:
        s.close()
    return ip


class RobotDog:
    """机器狗基础接口封装"""

    def __init__(
        self, name: str, robot_ip: str, local_port: int, local_ip: str | None = None
    ) -> None:
        self.name = name
        self.app = mc_sdk_zsl_1_py.HighLevel()
        if local_ip is None:
            local_ip = get_local_ip()
        self.app.initRobot(local_ip, local_port, robot_ip)

    def get_current_ctrl_mode(self) -> int:
        """获取当前控制模式

        Returns:
            int: 控制模式值
                - 0: 阻尼模式，设备未使能
                - 1: 站立状态/打招呼状态
                - 10: 设备趴下时触发电机自由状态
                - 18: 移动状态
                - 21: 动作状态（姿态模式、跳跃模式、双腿站立等）
                - 51: 趴下状态
        """
        return self.app.getCurrentCtrlmode()

    def stand_up(self, duration: float = 4.5):
        """站立（无论是否成功在日志中都显示状态值为 0）"""
        self._safe_action(action=self.app.standUp, action_name="standUp()")
        time.sleep(duration)

    def lie_down(self, duration: float = 2.5):
        """趴下（无论成功在日志中都显示状态值为 0）"""
        self._safe_action(action=self.app.lieDown, action_name="lieDown()")
        time.sleep(duration)

    def attitude_control(
        self,
        roll_rate: float = 0,
        pitch_rate: float = 0,
        yaw_rate: float = 0,
        height_vel: float = 0,
    ):
        """姿态控制（不传任何参数既是复位）

        Args:
            roll_rate (float): 绕 X 轴角速度（rad/s），∈ (-0.6, 0.6)
            pitch_rate (float): 绕 Y 轴角速度（rad/s），∈ (-0.6, 0.6)
            yaw_rate (float): 绕 Z 轴角速度（rad/s），∈ (-0.6, 0.6)
            height_vel (float): 垂直高度速度（m/s），∈ (-0.5, 0.5)

        Notes:
            1. roll_rate 向左侧倾为正，向右侧倾为负
            2. pitch_rate 低头为正，仰头为负
            3. yaw_rate 逆时针探头为正，顺时针探头为负
        """
        self._safe_action(
            action=lambda: self.app.attitudeControl(
                roll_rate, pitch_rate, yaw_rate, height_vel
            ),
            action_name=f"attitudeControl({roll_rate}, {pitch_rate}, {yaw_rate}, {height_vel})",
        )

    def move(self, vx: float = 0, vy: float = 0, yaw_rate: float = 0):
        """移动（不传任何参数既是停止）

        Args：
            vx (float): 前向速度（m/s），∈ (-3.0, -0.05) ∪ (0.05, 3.0)
            vy (float): 侧向速度（m/s），∈ (-1.0, -0.1) ∪ (0.1, 1.0)
            yaw_rate (float): 绕 Z 轴角速度（rad/s），yaw_rate ∈ (-3.0, -0.02) ∪ (0.02, 3.0)

        Notes:
            1. vx 向前为正，向后为负
            2. vy 向左为正，向右为负
            3. yaw_rate 逆时针为正，顺时针为负
        """
        self._safe_action(
            action=lambda: self.app.move(vx, vy, yaw_rate),
            action_name=f"move({vx}, {vy}, {yaw_rate})",
        )

    def jump(self, duration: float = 2.5):
        """跳跃"""
        self._safe_action(action=self.app.jump, action_name="jump()")
        time.sleep(duration)

    def front_jump(self, duration: float = 2.5):
        """前跳"""
        self._safe_action(action=self.app.frontJump, action_name="frontJump()")
        time.sleep(duration)

    def back_flip(self, duration: float = 2.5):
        """后空翻"""
        self._safe_action(action=self.app.backflip, action_name="backflip()")
        time.sleep(duration)

    def shake_hand(self, duration: float = 10):
        """握手"""
        self._safe_action(action=self.app.shakeHand, action_name="shakeHand()")
        time.sleep(duration)

    def _safe_action(
        self,
        action: callable,       # 动作函数的引用
        action_name: str = "",  # 动作名称
        interval: float = 0.2,  # 重试间隔（秒）
    ):
        """安全执行动作，直到成功为止

        Args:
            action (callable): 动作函数的引用
            interval (float): 重试间隔（秒）
            action_name (str): 动作名称（用于日志输出）
        """
        while True:
            result = action()  # 执行动作
            if result == 0:
                log("+", self.name, action_name, result)
                break
            else:
                log("-", self.name, action_name, f"{result}")
                time.sleep(interval)


class CrazyRobotDog(RobotDog):

    def lean_left(self, duration: float = 0.5, reset: float = 0):
        """左倾"""
        self.attitude_control(roll_rate=-0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def lean_right(self, duration: float = 0.5, reset: float = 0):
        """右倾"""
        self.attitude_control(roll_rate=0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def nod_up(self, duration: float = 0.5, reset: float = 0):
        """抬头"""
        self.attitude_control(pitch_rate=-0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def nod_down(self, duration: float = 0.5, reset: float = 0):
        """低头"""
        self.attitude_control(pitch_rate=0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def rotate_clockwise(self, duration: float = 0.5, reset: float = 0):
        """顺时针探头"""
        self.attitude_control(yaw_rate=-0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def rotate_counterclockwise(self, duration: float = 0.5, reset: float = 0):
        """逆时针探头"""
        self.attitude_control(yaw_rate=0.59)
        time.sleep(duration)
        if reset:
            self.attitude_control()
            time.sleep(reset)

    def attitude_rest(self, duration: float = 0.5):
        """恢复姿态"""
        self.attitude_control()
        time.sleep(duration)

    def max_height(self, duration: float = 0.5, _height_vel: float = 0.3):
        """调节腿关节以达到最大高度"""
        self.attitude_control(height_vel=_height_vel)
        time.sleep(duration)

    def min_height(self, duration: float = 0.5, _height_vel: float = -0.3):
        """调节腿关节以达到最小高度"""
        self.attitude_control(height_vel=_height_vel)
        time.sleep(duration)

    def move_by_distance(
        self,
        axis: Literal["x", "-x", "y", "-y"],
        distance: float,
        speed: float = 0.5,
    ):
        """按距离移动

        Args:
            axis (str):
                - "x": 前进
                - "-x": 后退
                - "y": 右移
                - "-y": 左移
            distance (float): 移动距离（m），∈ (0, ∞)
            speed (float): 移动速度（m/s)，默认 0.5 m/s
                - 前后移动时：speed ∈ (-3.0, -0.05) ∪ (0.05, 3.0)
                - 左右移动时：speed ∈ (-1.0, -0.1) ∪ (0.1, 1.0)

        Note:
            1. 速度大 + 距离小 -> 误差大
            2. 速度小 + 距离大 -> 误差小
            3. 起步和停止影响实际移动距离
        """
        duration = abs(distance) / speed  # 计算移动持续时间
        params = {}
        match axis:
            case "x":
                params["vx"] = speed
            case "-x":
                params["vx"] = -speed
            case "y":
                params["vy"] = speed
            case "-y":
                params["vy"] = -speed
        self.move(**params)
        time.sleep(duration)
        self.move()

    def turn_around(
        self,
        angle: float = 180.0,
        speed: float = 30,
        direction: Literal["cw", "ccw"] = "cw",
    ) -> None:
        """原地转身

        Args:
            angle: 转身角度（度），默认 180 度
            speed: 偏航角速度绝对值（度/秒），约 ∈ (2, 170)，默认 30 度/秒
            direction: 旋转方向，默认 "cw"
                - "cw": 顺时针
                - "ccw": 逆时针
        """
        # 将角度转换为弧度
        angle_rad = angle * math.pi / 180.0
        # 将 speed（deg/s）转换为 yaw_rate（rad/s）
        yaw_rate_rad = round(speed * math.pi / 180.0, 4)
        # 根据方向确定角速度符号
        actual_yaw_rate = -yaw_rate_rad if direction == "cw" else yaw_rate_rad
        # 计算旋转持续时间
        duration = round(abs(angle_rad) / abs(actual_yaw_rate), 4)

        # 执行旋转
        self.move(yaw_rate=actual_yaw_rate)
        time.sleep(duration)
        self.move()



