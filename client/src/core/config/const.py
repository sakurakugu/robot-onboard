from pathlib import Path
from typing import Any, Dict

import uuid6  # python3.11才自带uuid7，需要用第三方库

ORG_NAME = "sparkrobot"  # 公司组织名
APP_NAME = "robot-agent" # 这是放置在机器狗身上的代理，用于通过SDK控制机器人，并连接到服务器和APP，因此叫 “机器人-代理”
WORKSPACE_DIR = Path.home() / ORG_NAME

SERVER_ADDR = "192.168.0.108"      # 服务器地址
CONTROLLER_ADDR = "192.168.0.108"  # 手机App地址

__all__ = [
    "ORG_NAME",
    "APP_NAME",
    "WORKSPACE_DIR",
    "SERVER_ADDR",
    "CONTROLLER_ADDR",
]

# GLOBALS_CONFIG 全局配置
def get_globals_config(data: Dict[str, Any]) -> Dict[str, str]:
    uuid_val = data.get("uuid") or str(uuid6.uuid7())
    name_val = data.get("name") or f"机器狗-{uuid_val[:4]}"
    model_val = data.get("model") or "agibot-d1"
    version_val = data.get("version") or "0.0.0"
    return {
        "uuid": uuid_val,
        "name": name_val,
        "model": model_val,
        "version": version_val,
    }

DEFAULTS_CONFIG = { # 默认客户端配置
    "server": {
        # TODO: 到时候分离手机端和服务端后，将这里的地址修改
        "base_url": f"ws://{SERVER_ADDR}",         # 服务器基础URL
        "ws_path": "/api/v1/conversation/connect", # WebSocket路径
        "control_url": f"ws://{SERVER_ADDR}:9000/api/v1/conversation/connect",        # 控制URL
        "business_url": f"ws://{SERVER_ADDR}:9001/api/v1/conversation/connect",       # 业务URL
        "audio_upload_url": f"ws://{SERVER_ADDR}:9002/api/v1/conversation/connect",   # 音频上传URL
        "audio_download_url": f"ws://{SERVER_ADDR}:9003/api/v1/conversation/connect", # 音频下载URL
        "reconnect_interval": 5,  # 重连间隔（秒）
        "heartbeat_interval": 30, # 心跳间隔（秒）
    },
    "sdk": { # 这里一般保持不变（也是默认值）
        "robot_ip": "127.0.0.1",
        "local_port": 43988,
    },
    "audio": {
        "sample_rate": 16000,     # 音频采样率
        "channels": 1,            # 音频通道数（一般为1，单声道）
        "frame_duration_ms": 20,  # 音频帧时长（毫秒）
        "vad_threshold": 0.015,   # VAD阈值（用于语音活动检测）
        "vad_silence_ms": 800,    # VAD静音时长（毫秒）
        "max_segment_ms": 10000,  # 最大音频片段时长（毫秒）
        "enable_streaming": True, # 是否启用流式传输
        "input_device": None,     # 音频输入设备（None表示默认设备）
    },
    "actions": {
        "exit_behavior": "lie_down", # 退出后默认行为：lie_down | stand_up | stop
    },
    "logging": {
        "log_dir": str(WORKSPACE_DIR / "logs" / APP_NAME), # 日志目录
        "level": "INFO",                                   # 日志级别
        "max_file_size_mb": 10,                            # 每个日志文件最大大小（MB）
    },
}
