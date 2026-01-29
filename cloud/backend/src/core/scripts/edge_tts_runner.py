import sys
import json
import asyncio
import base64

import edge_tts


async def main():
    data = sys.stdin.read()
    payload = json.loads(data)
    text = payload.get("text", "")
    voice = payload.get("voice", "zh-CN-XiaoxiaoNeural")
    speed = payload.get("speed", 0)
    pitch = payload.get("pitch", 0)
    volume = payload.get("volume", 0)

    def fmt_signed_percent(n: int) -> str:
        s = int(n)
        return f"{'+' if s >= 0 else ''}{s}%"
    def fmt_signed_hz(n: int) -> str:
        s = int(n)
        return f"{'+' if s >= 0 else ''}{s}Hz"

    rate_opt = fmt_signed_percent(speed)
    pitch_opt = fmt_signed_hz(pitch)
    volume_opt = fmt_signed_percent(volume)

    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=rate_opt,
        pitch=pitch_opt,
        volume=volume_opt,
    )

    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    base64_audio = base64.b64encode(audio_bytes).decode("ascii")

    duration = 0

    print(json.dumps({"base64": base64_audio, "duration": duration, "format": "mp3"}))


if __name__ == "__main__":
    asyncio.run(main())
