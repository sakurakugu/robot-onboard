import asyncio
import os
import sys

# 将 src 目录添加到 sys.path，解决模块导入问题
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from src.application import main as robot_main


def main():
    try:
        asyncio.run(robot_main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
