import base64
import time
from typing import Any, Dict


def build_text_input(robot_uuid: str, text: str) -> Dict[str, Any]:
    """ 构建文本输入消息 """
    return {
        "type": "text_input",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000), # 毫秒级时间戳
        "data": {"text": text},
    }


def build_audio_start(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    frame_duration_ms: int, # 音频帧持续时间（毫秒）
    sample_rate: int,       # 采样率（赫兹）
    channels: int,          # 声道数
) -> Dict[str, Any]:
    """ 构建音频开始消息 """
    return {
        "type": "audio_start",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "format": "opus",
            "sampleRate": sample_rate,
            "channels": channels,
            "frameDurationMs": frame_duration_ms,
            "sessionId": session_id,
        },
    }


def build_audio_chunk(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    seq: int,               # 音频帧序号
    audio_bytes: bytes,     # 音频数据（Opus 编码）
    frame_duration_ms: int, # 音频帧持续时间（毫秒）
    sample_rate: int,       # 采样率（赫兹）
    channels: int,          # 声道数
) -> Dict[str, Any]:
    """ 构建音频帧消息 """
    return {
        "type": "audio_chunk",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "format": "opus",
            "sampleRate": sample_rate,
            "channels": channels,
            "frameDurationMs": frame_duration_ms,
            "sessionId": session_id,
            "seq": seq,
            "buffer": base64.b64encode(audio_bytes).decode("ascii"),
        },
    }


def build_audio_end(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    reason: str,            # 结束原因
) -> Dict[str, Any]:
    """ 构建音频结束消息 """
    return {
        "type": "audio_end",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "sessionId": session_id,
            "reason": reason,
        },
    }

# TODO: 到时候要传sn值、软件版本等，这里的部分作为metadata是机器人本身的数据，配置不要从这里传
def build_robot_register(
    robot_uuid: str,        # 机器人 UUID
    name: str,              # 机器人名称
    model: str,             # 机器人模型
    version: str,           # 机器人版本
) -> Dict[str, Any]:
    """ 构建机器人注册消息 """
    return {
        "type": "robot_register",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "name": name,
            "model": model,
            "version": version, # 运控版本（不是机器人软件版本）
            "metadata": {},
        },
    }


def build_heartbeat(robot_uuid: str) -> Dict[str, Any]:
    """ 构建心跳消息 """
    return {
        "type": "heartbeat",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {},
    }


def build_status(
    robot_uuid: str,        # 机器人 UUID
    seq: int | None,        # 状态序号（可选）
    data: Dict[str, Any],   # 状态数据
) -> Dict[str, Any]:
    """ 构建状态消息 """
    return {
        "type": "status",
        "robotId": robot_uuid,
        "seq": seq,
        "timestamp": int(time.time() * 1000),
        "data": data,
    }
