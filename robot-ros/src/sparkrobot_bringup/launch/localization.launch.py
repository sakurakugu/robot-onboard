from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    nav2_share = FindPackageShare("nav2_bringup")
    bringup_share = FindPackageShare("sparkrobot_bringup")
    default_params = PathJoinSubstitution([bringup_share, "config", "nav2.yaml"])

    localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([nav2_share, "launch", "localization_launch.py"])),
        launch_arguments={
            "map": LaunchConfiguration("map"),
            "params_file": LaunchConfiguration("params_file"),
            "use_sim_time": "false",
            "autostart": "true",
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("map", description="地图 yaml 文件路径"),
            DeclareLaunchArgument("params_file", default_value=default_params),
            localization_launch,
        ]
    )
