import base64
import time
from typing import Any, Dict


def build_text_input(robot_uuid: str, text: str) -> Dict[str, Any]:
    return {
        "type": "text_input",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {"text": text},
    }


def build_audio_start(
    robot_uuid: str, session_id: str, frame_duration_ms: int, sample_rate: int, channels: int
) -> Dict[str, Any]:
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
    robot_uuid: str,
    session_id: str,
    seq: int,
    audio_bytes: bytes,
    frame_duration_ms: int,
    sample_rate: int,
    channels: int,
) -> Dict[str, Any]:
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


def build_audio_end(robot_uuid: str, session_id: str, reason: str) -> Dict[str, Any]:
    return {
        "type": "audio_end",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "sessionId": session_id,
            "reason": reason,
        },
    }


def build_client_register(robot_uuid: str, name: str, model: str, version: str) -> Dict[str, Any]:
    return {
        "type": "client_register",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {
            "name": name,
            "model": model,
            "version": version,
            "metadata": {},
        },
    }


def build_heartbeat(robot_uuid: str) -> Dict[str, Any]:
    return {
        "type": "heartbeat",
        "robotId": robot_uuid,
        "timestamp": int(time.time() * 1000),
        "data": {},
    }


def build_status(robot_uuid: str, seq: int | None, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "status",
        "robot_id": robot_uuid,
        "seq": seq,
        "timestamp": int(time.time() * 1000),
        "data": data,
    }
