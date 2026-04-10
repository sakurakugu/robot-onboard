from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    package_share = FindPackageShare("sparkrobot_bringup")
    default_lidar_params = PathJoinSubstitution([package_share, "config", "lidar_n10p_ethernet.yaml"])

    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([package_share, "launch", "lidar.launch.py"])),
        launch_arguments={
            "params_file": LaunchConfiguration("lidar_params"),
        }.items(),
    )

    frames_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([package_share, "launch", "frames.launch.py"])),
        launch_arguments={
            "parent_frame": LaunchConfiguration("base_frame"),
            "child_frame": LaunchConfiguration("laser_frame"),
        }.items(),
    )

    runtime_bridge_node = Node(
        package="sparkrobot_nav_bridge",
        executable="runtime_bridge_node",
        name="sparkrobot_runtime_bridge",
        output="screen",
        condition=IfCondition(LaunchConfiguration("runtime_bridge_enabled")),
    )

    dog_bridge_node = Node(
        package="sparkrobot_dog_bridge",
        executable="dog_bridge_node",
        name="sparkrobot_dog_bridge",
        output="screen",
        condition=IfCondition(LaunchConfiguration("dog_bridge_enabled")),
        parameters=[
            {
                "cmd_vel_topic": LaunchConfiguration("dog_cmd_vel_topic"),
                "imu_topic": LaunchConfiguration("dog_imu_topic"),
                "odom_topic": LaunchConfiguration("dog_odom_topic"),
                "bridge_status_topic": LaunchConfiguration("dog_bridge_status_topic"),
                "base_frame": LaunchConfiguration("base_frame"),
                "odom_frame": LaunchConfiguration("dog_odom_frame"),
                "telemetry_url": LaunchConfiguration("dog_telemetry_url"),
                "status_hz": ParameterValue(LaunchConfiguration("dog_status_hz"), value_type=float),
                "report_bridge_status_to_server": ParameterValue(
                    LaunchConfiguration("dog_report_bridge_status_to_server"),
                    value_type=bool,
                ),
                "telemetry_udp_host": LaunchConfiguration("dog_telemetry_udp_host"),
                "telemetry_udp_port": ParameterValue(LaunchConfiguration("dog_telemetry_udp_port"), value_type=int),
                "publish_tf": ParameterValue(LaunchConfiguration("dog_publish_tf"), value_type=bool),
                "enable_motion_control": ParameterValue(LaunchConfiguration("dog_enable_motion_control"), value_type=bool),
                "auto_stand_up_on_startup": ParameterValue(
                    LaunchConfiguration("dog_auto_stand_up_on_startup"),
                    value_type=bool,
                ),
                "stand_up_wait_sec": ParameterValue(LaunchConfiguration("dog_stand_up_wait_sec"), value_type=float),
                "command_timeout_sec": ParameterValue(LaunchConfiguration("dog_command_timeout_sec"), value_type=float),
                "telemetry_offline_timeout_sec": ParameterValue(
                    LaunchConfiguration("dog_telemetry_offline_timeout_sec"),
                    value_type=float,
                ),
                "stop_on_telemetry_offline": ParameterValue(
                    LaunchConfiguration("dog_stop_on_telemetry_offline"),
                    value_type=bool,
                ),
                "emergency_stop_topic": LaunchConfiguration("dog_emergency_stop_topic"),
                "max_linear_x": ParameterValue(LaunchConfiguration("dog_max_linear_x"), value_type=float),
                "max_linear_y": ParameterValue(LaunchConfiguration("dog_max_linear_y"), value_type=float),
                "max_angular_z": ParameterValue(LaunchConfiguration("dog_max_angular_z"), value_type=float),
                "max_accel_x": ParameterValue(LaunchConfiguration("dog_max_accel_x"), value_type=float),
                "max_accel_y": ParameterValue(LaunchConfiguration("dog_max_accel_y"), value_type=float),
                "max_accel_z": ParameterValue(LaunchConfiguration("dog_max_accel_z"), value_type=float),
                "rotate_in_place_enabled": ParameterValue(
                    LaunchConfiguration("dog_rotate_in_place_enabled"),
                    value_type=bool,
                ),
                "rotate_in_place_angular_threshold": ParameterValue(
                    LaunchConfiguration("dog_rotate_in_place_angular_threshold"),
                    value_type=float,
                ),
                "rotate_in_place_linear_deadband": ParameterValue(
                    LaunchConfiguration("dog_rotate_in_place_linear_deadband"),
                    value_type=float,
                ),
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("lidar_params", default_value=default_lidar_params),
            DeclareLaunchArgument("base_frame", default_value="base_link"),
            DeclareLaunchArgument("laser_frame", default_value="laser"),
            DeclareLaunchArgument("runtime_bridge_enabled", default_value="true"),
            DeclareLaunchArgument("dog_bridge_enabled", default_value="true"),
            DeclareLaunchArgument("dog_cmd_vel_topic", default_value="/cmd_vel"),
            DeclareLaunchArgument("dog_imu_topic", default_value="/imu"),
            DeclareLaunchArgument("dog_odom_topic", default_value="/odom"),
            DeclareLaunchArgument("dog_bridge_status_topic", default_value="/sparkrobot/bridge_status"),
            DeclareLaunchArgument("dog_odom_frame", default_value="odom"),
            DeclareLaunchArgument("dog_telemetry_url", default_value="http://127.0.0.1:8080/api/v1/telemetry/full"),
            DeclareLaunchArgument("dog_status_hz", default_value="5.0"),
            DeclareLaunchArgument("dog_report_bridge_status_to_server", default_value="true"),
            DeclareLaunchArgument("dog_telemetry_udp_host", default_value="127.0.0.1"),
            DeclareLaunchArgument("dog_telemetry_udp_port", default_value="8080"),
            DeclareLaunchArgument("dog_publish_tf", default_value="true"),
            DeclareLaunchArgument("dog_enable_motion_control", default_value="true"),
            DeclareLaunchArgument("dog_auto_stand_up_on_startup", default_value="false"),
            DeclareLaunchArgument("dog_stand_up_wait_sec", default_value="3.0"),
            DeclareLaunchArgument("dog_command_timeout_sec", default_value="0.5"),
            DeclareLaunchArgument("dog_telemetry_offline_timeout_sec", default_value="1.5"),
            DeclareLaunchArgument("dog_stop_on_telemetry_offline", default_value="true"),
            DeclareLaunchArgument("dog_emergency_stop_topic", default_value="/sparkrobot/emergency_stop"),
            DeclareLaunchArgument("dog_max_linear_x", default_value="0.6"),
            DeclareLaunchArgument("dog_max_linear_y", default_value="0.4"),
            DeclareLaunchArgument("dog_max_angular_z", default_value="1.2"),
            DeclareLaunchArgument("dog_max_accel_x", default_value="0.8"),
            DeclareLaunchArgument("dog_max_accel_y", default_value="0.6"),
            DeclareLaunchArgument("dog_max_accel_z", default_value="1.5"),
            DeclareLaunchArgument("dog_rotate_in_place_enabled", default_value="true"),
            DeclareLaunchArgument("dog_rotate_in_place_angular_threshold", default_value="0.35"),
            DeclareLaunchArgument("dog_rotate_in_place_linear_deadband", default_value="0.05"),
            lidar_launch,
            frames_launch,
            runtime_bridge_node,
            dog_bridge_node,
        ]
    )
