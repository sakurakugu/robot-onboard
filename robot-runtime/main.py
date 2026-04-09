import asyncio
import os
import sys

# 将当前项目根目录放到最前面，确保优先导入本项目的 src 包
project_root = os.path.dirname(os.path.abspath(__file__))
common_src_root = os.path.abspath(os.path.join(project_root, "..", "sparkrobot-common", "src"))
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)
if common_src_root in sys.path:
    sys.path.remove(common_src_root)
sys.path.insert(0, common_src_root)

from src.application import main as runtime_main  # noqa: E402


def main() -> None:
    try:
        asyncio.run(runtime_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
