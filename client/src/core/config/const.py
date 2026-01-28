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
        "base_url": f"ws://{SERVER_ADDR}",
        "ws_path": "/api/v1/conversation/connect",
        "control_url": f"ws://{SERVER_ADDR}:9000/api/v1/conversation/connect",
        "business_url": f"ws://{SERVER_ADDR}:9001/api/v1/conversation/connect",
        "audio_upload_url": f"ws://{SERVER_ADDR}:9002/api/v1/conversation/connect",
        "audio_download_url": f"ws://{SERVER_ADDR}:9003/api/v1/conversation/connect",
        "reconnect_interval": 5,
        "heartbeat_interval": 30,
    },
    "sdk": {
        "robot_ip": "127.0.0.1",
        "local_port": 43988,
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "frame_duration_ms": 20,
        "vad_threshold": 0.015,
        "vad_silence_ms": 800,
        "max_segment_ms": 10000,
        "enable_streaming": True,
        "input_device": None,
    },
    "logging": {
        "log_dir": str(WORKSPACE_DIR / "logs" / APP_NAME),
        "level": "INFO",
        "max_file_size_mb": 10,
    },
}
