import asyncio

from application import main as robot_main


def main():
    asyncio.run(robot_main())

if __name__ == "__main__":
    main()
