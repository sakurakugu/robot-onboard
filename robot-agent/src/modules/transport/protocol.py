import base64
import time
from typing import Any, Dict


def 构建文本输入消息(robot_uuid: str, text: str) -> Dict[str, Any]:
    """ build_text_input """
    return {
        "type": "text_input",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000), # 毫秒级时间戳
        "data": {"text": text},
    }


def 构建音频开始消息(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    frame_duration_ms: int, # 音频帧持续时间（毫秒）
    sample_rate: int,       # 采样率（赫兹）
    channels: int,          # 声道数
) -> Dict[str, Any]:
    """ build_audio_start """
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


def 构建音频帧消息(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    seq: int,               # 音频帧序号
    audio_bytes: bytes,     # 音频数据（Opus 编码）
    frame_duration_ms: int, # 音频帧持续时间（毫秒）
    sample_rate: int,       # 采样率（赫兹）
    channels: int,          # 声道数
) -> Dict[str, Any]:
    """ build_audio_chunk """
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


def 构建音频结束消息(
    robot_uuid: str,        # 机器人 UUID
    session_id: str,        # 会话 ID
    reason: str,            # 结束原因
) -> Dict[str, Any]:
    """ build_audio_end """
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
def 构建机器人注册消息(
    robot_uuid: str,                # 机器人 UUID
    name: str,                      # 机器人名称
    model: str,                     # 机器人模型
    agent_version: str,             # Agent 版本（robot-agent 软件版本）
) -> Dict[str, Any]:
    """ build_robot_register """
    return {
        "type": "robot_register",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "name": name,
            "model": model,
            "version": agent_version,
            "metadata": {},
        },
    }


def 构建心跳消息(robot_uuid: str) -> Dict[str, Any]:
    """ build_heartbeat """
    return {
        "type": "heartbeat",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {},
    }


def 构建状态消息(
    robot_uuid: str,        # 机器人 UUID
    seq: int | None,        # 状态序号（可选）
    data: Dict[str, Any],   # 状态数据
) -> Dict[str, Any]:
    """ build_status """
    return {
        "type": "status",
        "robotId": robot_uuid,
        "seq": seq,
        "timestamp": int(time.time() * 1000),
        "data": data,
    }


def 构建拍照响应消息(
    robot_uuid: str,        # 机器人 UUID
    request_id: str,        # 请求ID
    success: bool,          # 是否成功
    image: str | None = None,  # base64编码的图片（成功时）
    error: str | None = None,  # 错误信息（失败时）
) -> Dict[str, Any]:
    """ build_camera_response """
    return {
        "type": "camera_response",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "requestId": request_id,
            "success": success,
            "image": image,
            "format": "jpeg" if image else None,
            "error": error,
        },
    }


def 构建音量响应消息(
    robot_uuid: str,        # 机器人 UUID
    request_id: str,        # 请求ID
    success: bool,          # 是否成功
    data: dict | None = None,  # 响应数据
    error: str | None = None,  # 错误信息（失败时）
) -> Dict[str, Any]:
    """ build_volume_response """
    return {
        "type": "volume_response",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "requestId": request_id,
            "success": success,
            "data": data,
            "error": error,
        },
    }


def 构建配置响应消息(
    robot_uuid: str,        # 机器人 UUID
    request_id: str,        # 请求ID
    success: bool,          # 是否成功
    data: dict | None = None,  # 响应数据
    error: str | None = None,  # 错误信息（失败时）
) -> Dict[str, Any]:
    """ build_config_response """
    return {
        "type": "config_response",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "requestId": request_id,
            "success": success,
            "data": data,
            "error": error,
        },
    }


def 构建SDK模式响应消息(
    robot_uuid: str,        # 机器人 UUID
    request_id: str,        # 请求ID
    success: bool,          # 是否成功
    sdk_mode: bool | None = None,  # SDK模式状态
    error: str | None = None,  # 错误信息（失败时）
) -> Dict[str, Any]:
    """ build_sdk_mode_response """
    return {
        "type": "sdk_mode_response",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "requestId": request_id,
            "success": success,
            "sdkMode": sdk_mode,
            "error": error,
        },
    }
