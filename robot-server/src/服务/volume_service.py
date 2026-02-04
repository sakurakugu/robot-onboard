"""
音量管理服务 - 负责系统音量的获取和设置

使用 pactl 命令控制 PulseAudio 系统音量
"""
import os
import re
import subprocess


class VolumeService:
    """音量服务 - 使用 pactl 控制系统音量"""

    def _获取环境变量(self) -> dict:
        """
        获取 pactl 命令需要的环境变量
        
        Returns:
            dict: 包含必要环境变量的字典
        """
        env = os.environ.copy()
        
        # 如果 XDG_RUNTIME_DIR 不存在，尝试设置默认值
        if 'XDG_RUNTIME_DIR' not in env:
            # 通常是 /run/user/UID
            uid = os.getuid() if hasattr(os, 'getuid') else 1000
            env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
        
        return env

    def 获取音量(self) -> int:
        """
        获取当前系统音量（0-100）

        Returns:
            int: 音量百分比 (0-100)

        Raises:
            RuntimeError: 获取音量失败
        """
        try:
            # 获取默认音频输出设备的音量
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
                check=True,
                env=self._获取环境变量(),
            )

            # 解析输出，例如: "Volume: front-left: 65536 / 100% / 0.00 dB,   front-right: 65536 / 100% / 0.00 dB"
            output = result.stdout.strip()
            match = re.search(r"(\d+)%", output)

            if match:
                volume = int(match.group(1))
                return volume
            else:
                raise RuntimeError(f"无法解析音量输出: {output}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"获取音量失败: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("pactl 命令不存在，请确保已安装 PulseAudio") from None

    def 设置音量(self, volume: int) -> bool:
        """
        设置系统音量

        Args:
            volume: 音量百分比 (0-100)

        Returns:
            bool: 设置是否成功

        Raises:
            ValueError: 音量值超出范围
            RuntimeError: 设置音量失败
        """
        if not 0 <= volume <= 100:
            raise ValueError(f"音量值必须在 0-100 之间，当前值: {volume}")

        try:
            # 设置音量
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
                capture_output=True,
                text=True,
                check=True,
                env=self._获取环境变量(),
            )
            return True

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"设置音量失败: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("pactl 命令不存在，请确保已安装 PulseAudio") from None

    def 获取静音状态(self) -> bool:
        """
        获取静音状态

        Returns:
            bool: True 表示静音，False 表示未静音

        Raises:
            RuntimeError: 获取静音状态失败
        """
        try:
            result = subprocess.run(
                ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
                check=True,
                env=self._获取环境变量(),
            )

            # 输出格式: "Mute: yes" 或 "Mute: no"
            output = result.stdout.strip().lower()
            return "yes" in output

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"获取静音状态失败: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("pactl 命令不存在，请确保已安装 PulseAudio") from None

    def 设置静音(self, mute: bool) -> bool:
        """
        设置静音状态

        Args:
            mute: True 表示静音，False 表示取消静音

        Returns:
            bool: 设置是否成功

        Raises:
            RuntimeError: 设置静音失败
        """
        try:
            value = "1" if mute else "0"
            subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", value],
                capture_output=True,
                text=True,
                check=True,
                env=self._获取环境变量(),
            )
            return True

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"设置静音失败: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("pactl 命令不存在，请确保已安装 PulseAudio") from None

    def 获取音量信息(self) -> dict:
        """
        获取完整的音量信息

        Returns:
            dict: 包含音量和静音状态的字典
        """
        return {
            "volume": self.获取音量(),
            "muted": self.获取静音状态(),
        }


# 单例模式
_volume_service_instance: VolumeService | None = None


def 获取音量服务单例() -> VolumeService:
    """获取音量服务单例"""
    global _volume_service_instance
    if _volume_service_instance is None:
        _volume_service_instance = VolumeService()
    return _volume_service_instance
