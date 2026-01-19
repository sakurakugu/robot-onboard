from typing import Literal
import time
import math
from .core import RobotDog

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
        distance: float,    # 移动距离（m），∈ (0, ∞)
        speed: float = 0.5, # 移动速度（m/s)，默认 0.5 m/s
                # 前后移动时：speed ∈ (-3.0, -0.05) ∪ (0.05, 3.0)
                # 左右移动时：speed ∈ (-1.0, -0.1) ∪ (0.1, 1.0)
    ):
        """
        按距离移动
        
        Note:
            1. 速度大 + 距离小 -> 误差大
            2. 速度小 + 距离大 -> 误差小
            3. 起步和停止影响实际移动距离
        """
        duration = abs(distance) / speed # 计算移动持续时间
        params = {}
        match axis:
            case "x":  # 前进
                params["vx"] = speed
            case "-x": # 后退
                params["vx"] = -speed
            case "y":  # 右移
                params["vy"] = speed
            case "-y": # 左移
                params["vy"] = -speed
        self.move(**params)
        time.sleep(duration)
        self.move()

    def turn_around(
        self,
        angle: float = 180.0, # 转身角度（度），默认 180 度
        speed: float = 30,    # 偏航角速度绝对值（度/秒），约 ∈ (2, 170)，默认 30 度/秒
        direction: Literal["cw", "ccw"] = "cw", # 旋转方向，默认 "cw(顺时针)"
    ) -> None:
        """原地转身"""
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

__all__ = ["CrazyRobotDog"]

