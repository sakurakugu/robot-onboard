from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode


def generate_launch_description() -> LaunchDescription:
    params_file = LaunchConfiguration("params_file")

    driver_node = LifecycleNode(
        package="lslidar_driver",
        executable="lslidar_driver_node",
        name="lslidar_driver_node",
        namespace="",
        output="screen",
        emulate_tty=True,
        parameters=[params_file],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                description="激光雷达参数文件路径",
            ),
            driver_node,
        ]
    )
