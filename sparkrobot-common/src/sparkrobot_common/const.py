"""
常量和配置字段定义

配置格式说明（一层嵌套）：
- 使用 [section] 表示分组
- 只允许 key = value 或 key = [array] 两种形式
- 只有一层嵌套，不会出现 [section.subsection]
- 所有配置项必须有默认值，不允许空值
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _生成UUID() -> str:
    """生成 UUID7"""
    try:
        import uuid6
        return str(uuid6.uuid7())
    except ImportError:
        import uuid
        return str(uuid.uuid7()) # type: ignore[attr-defined]


# ==================== 基础常量 ====================

ORG_NAME = "sparkrobot"  # 组织名
WORKSPACE_DIR = Path.home() / ORG_NAME
CONFIG_DIR = WORKSPACE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# robot-server 配置
ROBOT_SERVER_HOST = "127.0.0.1"
ROBOT_SERVER_PORT = 8080
ROBOT_SERVER_URL = f"http://{ROBOT_SERVER_HOST}:{ROBOT_SERVER_PORT}"

# 默认服务器地址
DEFAULT_SERVER_ADDR = "106.53.174.61"
MEDIA_PUBLISH_BASE_URL_AUTO = "follow_server"


# ==================== 配置字段定义 ====================

@dataclass
class 配置字段:
    """配置字段定义"""
    section: str      # 所属分组
    key: str          # 字段名
    default: Any      # 默认值
    description: str  # 描述
    value_type: str   # "string", "int", "float", "bool", "list"
    readonly: bool = False  # 是否只读
    options: list[str] | None = None  # 可选项

# 配置分组标题映射
CONFIG_SECTION_TITLES: dict[str, str] = {
    "robot": "机器人信息",
    "cloud": "云端连接配置",
    "studio": "电脑端连接配置",
    "media": "视频流媒体",
    "sdk": "SDK配置",
    "lidar": "激光雷达配置",
    "frames": "坐标系配置",
    "mapping": "建图配置",
    "localization": "定位配置",
    "navigation": "导航配置",
    "patrol": "巡逻配置",
    "audio": "音频配置",
    "actions": "动作配置",
    "logging": "日志配置",
    "auth": "认证配置",
}

# 默认配置字段定义（一层嵌套结构）
DEFAULT_CONFIG_FIELDS: list[配置字段] = [
    # 机器人基本信息 [robot]
    配置字段("robot", "uuid", "", "机器人唯一标识（自动生成）", "string", readonly=True),
    配置字段("robot", "name", "", "机器人名称", "string"),
    配置字段("robot", "model", "agibot-d1", "机器人型号", "string", readonly=True),
    配置字段("robot", "agent_version", "0.0.0", "机器人代理版本", "string", readonly=True),
    配置字段("robot", "server_version", "0.0.0", "robot-server 版本", "string", readonly=True),
    配置字段("robot", "motion_control_version", "0.0.0", "机器人运控版本", "string", readonly=True),

    # 云端连接配置 [cloud]
    配置字段("cloud", "enabled", True, "是否启用云端连接", "bool"),
    配置字段("cloud", "server_url", DEFAULT_SERVER_ADDR, "云端服务器地址（只填主机或主机:端口，连接时自动补 ws://）", "string"),
    配置字段("cloud", "business_url", "/api/v1/robot/business", "云端业务连接URL", "string"),
    配置字段("cloud", "audio_upload_url", "/api/v1/robot/audio/upload", "云端音频上传URL", "string"),
    配置字段("cloud", "audio_download_url", "/api/v1/robot/audio/download", "云端音频下载URL", "string"),
    配置字段("cloud", "reconnect_interval", 5, "云端重连间隔（秒）", "int"),
    配置字段("cloud", "heartbeat_interval", 30, "云端心跳间隔（秒）", "int"),

    # 电脑端连接配置 [studio]
    配置字段("studio", "enabled", False, "是否启用电脑端工作站连接", "bool"),
    配置字段("studio", "server_url", "", "电脑端工作站地址（只填主机或主机:端口，连接时自动补 ws://）", "string"),
    配置字段("studio", "business_url", "/api/v1/web/business", "电脑端业务连接URL", "string"),
    配置字段("studio", "reconnect_interval", 5, "电脑端重连间隔（秒）", "int"),
    配置字段("studio", "heartbeat_interval", 15, "电脑端心跳间隔（秒）", "int"),

    # 视频流媒体配置 [media]
    配置字段("media", "enable_cloud_streaming", True, "是否启用云端正式视频推流", "bool"),
    配置字段("media", "stream_on_demand", True, "是否启用按需推流（无人观看时停止 ffmpeg）", "bool"),
    配置字段("media", "source_rtsp_url", "rtsp://127.0.0.1:8554/test", "本地 RTSP 视频源地址", "string"),
    配置字段("media", "publish_base_url", MEDIA_PUBLISH_BASE_URL_AUTO, "云端 MediaMTX RTSP 推流地址，默认跟随 cloud.server_url 主机", "string"),
    配置字段("media", "stream_path_prefix", "robots", "云端媒体流路径前缀", "string"),
    配置字段("media", "publish_user", "robotdog", "云端媒体推流用户名", "string"),
    配置字段("media", "publish_pass", "robotdog", "云端媒体推流密码", "string"),
    配置字段("media", "ffmpeg_path", "ffmpeg", "ffmpeg 可执行文件路径", "string"),
    配置字段("media", "rtsp_transport", "tcp", "RTSP 传输方式：tcp|udp", "string", options=["tcp", "udp"]),
    配置字段("media", "ffmpeg_loglevel", "warning", "ffmpeg 日志级别", "string", options=["quiet", "error", "warning", "info"]),

    # SDK配置 [sdk]
    配置字段("sdk", "enable_sdk_on_startup", True, "启动时是否开启SDK模式", "bool"),
    配置字段("sdk", "robot_ip", "127.0.0.1", "机器人SDK IP地址", "string", readonly=True),
    配置字段("sdk", "local_port", 43988, "本地SDK端口", "int", readonly=True),

    # 激光雷达配置 [lidar]
    配置字段("lidar", "enabled", False, "是否启用 2D 激光雷达", "bool"),
    配置字段("lidar", "transport", "ethernet", "雷达传输方式：ethernet|serial", "string", options=["ethernet", "serial"]),
    配置字段("lidar", "device_model", "n10p", "激光雷达型号", "string"),
    配置字段("lidar", "serial_port", "/dev/wheeltec_laser", "雷达串口设备路径", "string"),
    配置字段("lidar", "baud_rate", 460800, "雷达串口波特率", "int"),
    配置字段("lidar", "device_ip", "192.168.168.200", "网口版雷达设备 IP", "string"),
    配置字段("lidar", "host_ip", "192.168.168.168", "本机用于接收网口雷达数据的 IP", "string"),
    配置字段("lidar", "msop_port", 2368, "网口雷达数据接收端口", "int"),
    配置字段("lidar", "difop_port", 2369, "网口雷达控制端口", "int"),
    配置字段("lidar", "frame_id", "laser", "雷达坐标系名称", "string"),
    配置字段("lidar", "angle_disable_min", 0.0, "雷达屏蔽角度起点", "float"),
    配置字段("lidar", "angle_disable_max", 0.0, "雷达屏蔽角度终点", "float"),
    配置字段("lidar", "min_range", 0.2, "雷达最小有效距离（米）", "float"),
    配置字段("lidar", "max_range", 25.0, "雷达最大有效距离（米）", "float"),

    # 坐标系配置 [frames]
    配置字段("frames", "base_frame", "base_link", "机器人机体坐标系", "string"),
    配置字段("frames", "odom_frame", "odom", "里程计坐标系", "string"),
    配置字段("frames", "map_frame", "map", "地图坐标系", "string"),
    配置字段("frames", "laser_frame", "laser", "激光雷达坐标系", "string"),

    # 建图配置 [mapping]
    配置字段("mapping", "enabled", False, "是否启用建图能力", "bool"),
    配置字段("mapping", "backend", "slam_toolbox", "建图后端名称", "string"),
    配置字段("mapping", "map_save_dir", str(WORKSPACE_DIR / "maps"), "地图保存目录", "string"),
    配置字段("mapping", "auto_save_on_stop", True, "结束建图时是否自动保存地图", "bool"),

    # 定位配置 [localization]
    配置字段("localization", "enabled", False, "是否启用定位能力", "bool"),
    配置字段("localization", "backend", "amcl", "定位后端名称", "string"),
    配置字段("localization", "default_map", "", "默认加载的地图名称", "string"),
    配置字段("localization", "relocalization_on_start", False, "启动时是否尝试重定位", "bool"),

    # 导航配置 [navigation]
    配置字段("navigation", "enabled", False, "是否启用导航能力", "bool"),
    配置字段("navigation", "backend", "nav2", "导航后端名称", "string"),
    配置字段("navigation", "cmd_vel_topic", "/cmd_vel", "导航速度控制话题", "string"),
    配置字段("navigation", "goal_timeout_sec", 120, "导航目标超时时间（秒）", "int"),
    配置字段("navigation", "goal_tolerance_xy", 0.15, "导航到点平面容差（米）", "float"),
    配置字段("navigation", "goal_tolerance_yaw", 0.2, "导航到点偏航容差（弧度）", "float"),

    # 巡逻配置 [patrol]
    配置字段("patrol", "enabled", False, "是否启用巡逻能力", "bool"),
    配置字段("patrol", "waypoint_dir", str(WORKSPACE_DIR / "waypoints"), "巡逻点位目录", "string"),
    配置字段("patrol", "default_linear_speed", 0.3, "巡逻默认线速度（米每秒）", "float"),
    配置字段("patrol", "default_angular_speed", 0.5, "巡逻默认角速度（弧度每秒）", "float"),
    配置字段("patrol", "arrival_wait_sec", 2.0, "到达点位后的停留时间（秒）", "float"),
    配置字段("patrol", "loop", False, "巡逻是否循环执行", "bool"),

    # 音频配置 [audio]
    配置字段("audio", "sample_rate", 16000, "音频采样率", "int"),
    配置字段("audio", "channels", 1, "音频通道数", "int"),
    配置字段("audio", "frame_duration_ms", 20, "音频帧时长（毫秒）", "int"),
    配置字段("audio", "vad_threshold", 0.015, "VAD阈值", "float"),
    配置字段("audio", "vad_silence_ms", 800, "VAD静音时长（毫秒）", "int"),
    配置字段("audio", "max_segment_ms", 30000, "最大音频片段时长（毫秒）", "int"),  # 从10000增加到30000ms
    配置字段("audio", "enable_streaming", False, "是否启用流式传输", "bool"),  # 改为False，禁用流式传输以支持一次性收集
    配置字段("audio", "input_device", "", "音频输入设备（空表示默认）", "string"),

    # 动作配置 [actions]
    配置字段("actions", "startup_behavior", "stop", "启动后状态：stop|lie_down|stand_up", "string", options=["stop", "lie_down", "stand_up"]),
    配置字段("actions", "exit_behavior", "lie_down", "退出后行为：lie_down|stand_up|stop", "string", options=["lie_down", "stand_up", "stop"]),

    # 日志配置 [logging]
    配置字段("logging", "level", "INFO", "日志级别：DEBUG|INFO|WARNING|ERROR", "string", options=["DEBUG", "INFO", "WARNING", "ERROR"]),
    配置字段("logging", "max_file_size_mb", 10, "日志文件最大大小（MB）", "int"),

    # 认证配置 [auth]
    配置字段("auth", "username", "sparkrobot", "登录用户名", "string", readonly=True),
    配置字段("auth", "password", "sparkrobot", "登录密码", "string", readonly=True),
    配置字段("auth", "session_timeout", 3600, "会话超时时间（秒）", "int"),
]

# 只读字段集合
READONLY_FIELDS: set[str] = {f"{f.section}.{f.key}" for f in DEFAULT_CONFIG_FIELDS if f.readonly}


# ==================== 配置工具函数 ====================

def _生成机器人名称(uuid_val: str) -> str:
    """生成机器人名称"""
    return f"机器狗-{uuid_val[:4]}"


def 获取所有分组() -> list[str]:
    """获取所有配置分组（保持顺序）"""
    seen: list[str] = []
    for f in DEFAULT_CONFIG_FIELDS:
        if f.section not in seen:
            seen.append(f.section)
    return seen


def 获取默认配置() -> dict[str, dict[str, Any]]:
    """获取默认配置字典（嵌套格式）"""
    config: dict[str, dict[str, Any]] = {}

    # 先生成 UUID
    uuid_val = _生成UUID()

    for field in DEFAULT_CONFIG_FIELDS:
        if field.section not in config:
            config[field.section] = {}

        if field.section == "robot" and field.key == "uuid":
            config[field.section][field.key] = uuid_val
        elif field.section == "robot" and field.key == "name":
            config[field.section][field.key] = _生成机器人名称(uuid_val)
        else:
            config[field.section][field.key] = field.default

    return config


def 获取字段信息(section: str, key: str) -> 配置字段 | None:
    """获取字段信息"""
    for field in DEFAULT_CONFIG_FIELDS:
        if field.section == section and field.key == key:
            return field
    return None


def 通过完整键名获取字段信息(full_key: str) -> 配置字段 | None:
    """通过完整键名获取字段信息"""
    if "." not in full_key:
        return None
    section, key = full_key.split(".", 1)
    return 获取字段信息(section, key)


def 获取配置项字段信息() -> list[dict[str, Any]]:
    """获取配置字段信息（用于前端展示）"""
    return [
        {
            "section": f.section,
            "key": f.key,
            "full_key": f"{f.section}.{f.key}",
            "default": f.default,
            "description": f.description,
            "type": f.value_type,
            "readonly": f.readonly,
            "options": f.options,
        }
        for f in DEFAULT_CONFIG_FIELDS
    ]


def 获取配置分组信息() -> list[dict[str, Any]]:
    """获取配置分组信息（用于前端展示），包含分组名、标题和有序字段列表"""
    sections: dict[str, dict[str, Any]] = {}
    for f in DEFAULT_CONFIG_FIELDS:
        if f.section not in sections:
            sections[f.section] = {
                "section": f.section,
                "title": CONFIG_SECTION_TITLES.get(f.section, f.section),
                "keys": [],
            }
        sections[f.section]["keys"].append(f.key)
    return list(sections.values())


__all__ = [
    "ORG_NAME",
    "WORKSPACE_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEFAULT_SERVER_ADDR",
    "MEDIA_PUBLISH_BASE_URL_AUTO",
    "DEFAULT_CONFIG_FIELDS",
    "ROBOT_SERVER_HOST",
    "ROBOT_SERVER_PORT",
    "ROBOT_SERVER_URL",
    "READONLY_FIELDS",
    "配置字段",
    "获取所有分组",
    "获取默认配置",
    "获取字段信息",
    "通过完整键名获取字段信息",
    "获取配置项字段信息",
    "CONFIG_SECTION_TITLES",
    "获取配置分组信息",
]
