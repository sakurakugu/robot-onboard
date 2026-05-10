from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class 健康状态:
    在线: bool = False
    电量: int | None = None
    温度: float | None = None
    SDK模式: bool = False
    控制模式: str = "unknown"
    运动模式: str = "unknown"


@dataclass
class 运控桥状态:
    在线: bool = False
    运动控制启用: bool = False
    SDK就绪: bool = False
    遥测在线: bool = False
    允许运动: bool = False
    急停: bool = False
    裁决原因: str = "unknown"
    指令延迟秒: float | None = None
    遥测延迟秒: float | None = None
    目标速度: dict[str, float] = field(default_factory=lambda: {"vx": 0.0, "vy": 0.0, "wz": 0.0})
    输出速度: dict[str, float] = field(default_factory=lambda: {"vx": 0.0, "vy": 0.0, "wz": 0.0})


@dataclass
class 位姿状态:
    坐标系: str = "map"
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    置信度: float | None = None
    四元数: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])


@dataclass
class 里程状态:
    坐标系: str = "odom"
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    偏航角速度: float = 0.0


@dataclass
class IMU状态:
    欧拉角: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    加速度: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    角速度: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])


@dataclass
class 激光雷达状态:
    启用: bool = False
    已连接: bool = False
    传输方式: str = "ethernet"
    坐标系: str = "laser"
    扫描正常: bool = False
    频率: float | None = None


@dataclass
class 建图状态:
    状态: str = "idle"
    当前地图: str = ""
    最近地图: str | None = None
    保存目录: str = ""
    自动保存: bool = False


@dataclass
class 定位状态:
    状态: str = "idle"
    地图名称: str = ""
    置信度: float | None = None


@dataclass
class 导航状态:
    状态: str = "idle"
    当前目标: dict[str, Any] | None = None
    剩余距离: float | None = None
    失败原因: str | None = None


@dataclass
class 任务状态:
    状态: str = "idle"
    任务类型: str | None = None
    任务ID: str | None = None


@dataclass
class 手动控制状态:
    会话ID: str | None = None
    模式: str = "move"
    来源: str | None = None
    激活: bool = False
    速度: dict[str, float] = field(default_factory=lambda: {"vx": 0.0, "vy": 0.0, "wz": 0.0})
    更新时间戳毫秒: int | None = None


@dataclass
class 动作控制状态:
    动作名称: str | None = None
    状态: str = "idle"
    来源: str | None = None
    参数: dict[str, Any] = field(default_factory=dict)
    动作ID: str | None = None
    更新时间戳毫秒: int | None = None


@dataclass
class 控制域状态:
    当前控制源: str = "idle"
    当前控制模式: str = "idle"
    急停: bool = False
    允许运动: bool = False
    仲裁原因: str = "idle"
    手动控制: 手动控制状态 = field(default_factory=手动控制状态)
    动作控制: 动作控制状态 = field(default_factory=动作控制状态)


@dataclass
class 机器人状态快照:
    健康: 健康状态 = field(default_factory=健康状态)
    运控桥: 运控桥状态 = field(default_factory=运控桥状态)
    位姿: 位姿状态 = field(default_factory=位姿状态)
    里程: 里程状态 = field(default_factory=里程状态)
    IMU: IMU状态 = field(default_factory=IMU状态)
    激光雷达: 激光雷达状态 = field(default_factory=激光雷达状态)
    建图: 建图状态 = field(default_factory=建图状态)
    定位: 定位状态 = field(default_factory=定位状态)
    导航: 导航状态 = field(default_factory=导航状态)
    任务: 任务状态 = field(default_factory=任务状态)
    控制域: 控制域状态 = field(default_factory=控制域状态)

    def 导出字典(self) -> dict[str, Any]:
        """导出为字典。"""
        return asdict(self)
