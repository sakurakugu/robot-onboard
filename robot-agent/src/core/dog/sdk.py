import platform
import sys
from pathlib import Path

# 根据平台和架构选择对应的静态库的路径
machine = platform.machine().lower()
arch = "aarch64" if ("aarch64" in machine or "arm64" in machine) else "x86_64"
lib_dir = Path(__file__).parent / "lib" / "zsl-1" / arch
sys.path.insert(0, str(lib_dir))

try:
    import mc_sdk_zsl_1_py as 小型点足狗SDK
except ImportError as e:
    raise ImportError(f"无法导入 mc_sdk_zsl_1_py，请检查 {lib_dir} 下是否存在 .so 文件") from e

sys.modules[__name__] = 小型点足狗SDK
