import asyncio

from application import main as robot_main


def main():
    try:
        asyncio.run(robot_main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
