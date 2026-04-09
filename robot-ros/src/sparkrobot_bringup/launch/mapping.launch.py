from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    slam_toolbox_share = FindPackageShare("slam_toolbox")
    bringup_share = FindPackageShare("sparkrobot_bringup")
    default_params = PathJoinSubstitution([bringup_share, "config", "slam_toolbox_online_async.yaml"])

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([slam_toolbox_share, "launch", "online_async_launch.py"])),
        launch_arguments={
            "slam_params_file": LaunchConfiguration("slam_params_file"),
            "use_sim_time": "false",
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("slam_params_file", default_value=default_params),
            slam_launch,
        ]
    )
