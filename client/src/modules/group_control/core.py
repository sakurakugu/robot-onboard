import time

from core.dog import sdk
from core.logger import logger
from core.utils import get_local_ip


class RobotDog:
    """机器狗基础接口封装"""

    def __init__(self, name: str, robot_ip: str, local_port: int, local_ip: str | None = None) -> None:
        self.name = name
        self.app = sdk.HighLevel()
        if local_ip is None:
            local_ip = get_local_ip()
        self.app.initRobot(local_ip, local_port, robot_ip)

    def get_current_ctrl_mode(self) -> int:
        """获取当前控制模式

        Returns:
            int: 控制模式值
                - 0: 阻尼模式，设备未开启
                - 1: 站立状态/打招呼状态
                - 10: 设备趴下时触发电机自由状态
                - 18: 移动状态
                - 21: 动作状态（姿态模式、跳跃模式、双腿站立等）
                - 51: 趴下状态
        """
        return self.app.getCurrentCtrlmode()

    def stand_up(self, duration: float = 4.5):
        """站立（无论是否成功在日志中都显示状态值为 0）"""
        self._safe_action(action=self.app.standUp, action_name="站立")
        time.sleep(duration)

    def lie_down(self, duration: float = 2.5):
        """趴下（无论成功在日志中都显示状态值为 0）"""
        self._safe_action(action=self.app.lieDown, action_name="趴下")
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
            roll_rate (float) : 绕 X 轴角速度（rad/s），∈ (-0.6, 0.6)
            pitch_rate (float): 绕 Y 轴角速度（rad/s），∈ (-0.6, 0.6)
            yaw_rate (float)  : 绕 Z 轴角速度（rad/s），∈ (-0.6, 0.6)
            height_vel (float): 垂直高度速度（m/s），∈ (-0.5, 0.5)

        Notes:
            1. roll_rate 向左侧倾为正，向右侧倾为负
            2. pitch_rate 低头为正，仰头为负
            3. yaw_rate 逆时针探头为正，顺时针探头为负
        """
        self._safe_action(
            action=lambda: self.app.attitudeControl(roll_rate, pitch_rate, yaw_rate, height_vel),
            action_name="姿态控制({roll_rate}, {pitch_rate}, {yaw_rate}, {height_vel})",
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
            action_name="移动({vx}, {vy}, {yaw_rate})",
        )

    def jump(self, duration: float = 2.5):
        """跳跃"""
        self._safe_action(action=self.app.jump, action_name="跳跃")
        time.sleep(duration)

    def front_jump(self, duration: float = 2.5):
        """前跳"""
        self._safe_action(action=self.app.frontJump, action_name="前跳")
        time.sleep(duration)

    def back_flip(self, duration: float = 2.5):
        """后空翻"""
        self._safe_action(action=self.app.backflip, action_name="后空翻")
        time.sleep(duration)

    def shake_hand(self, duration: float = 10):
        """握手"""
        self._safe_action(action=self.app.shakeHand, action_name="握手")
        time.sleep(duration)

    def _safe_action(
        self,
        action: callable,  # 动作函数的引用
        action_name: str = "",  # 动作名称
        interval: float = 0.2,  # 重试间隔（秒）
    ):
        """安全执行动作，直到成功为止"""
        while True:
            result = action()
            message = f"[狗{self.name}] {action_name} -> {'成功' if result == 0 else '失败'}，状态值：{result}"
            if result == 0:
                logger.info(message)
                break
            else:
                logger.warning(message)
                time.sleep(interval)


__all__ = ["RobotDog"]
