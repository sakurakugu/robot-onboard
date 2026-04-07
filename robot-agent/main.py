import asyncio
import os
import sys

# 将当前项目根目录放到最前面，确保优先导入本项目的 src 包
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

from src.application import main as robot_main  # noqa: E402


def main():
    try:
        asyncio.run(robot_main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
