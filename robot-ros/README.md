# robot-ros

机器狗 2D 激光雷达、建图、定位、导航相关的 ROS2 工作空间。

当前阶段已提供：

- `sparkrobot_bringup`：统一封装 N10P 雷达、TF、SLAM、Nav2 的 launch 入口
- `sparkrobot_nav_bridge`：提供 `robot-runtime <-> Nav2` 的本地导航桥接节点
- `sparkrobot_dog_bridge`：提供 `cmd_vel -> 机器狗 SDK`、`telemetry -> /imu /odom /tf` 的桥接节点
- N10P 串口版 / 网口版参数模板
- `slam_toolbox` 与 `nav2` 的初始参数骨架

当前阶段未直接内置厂商源码，原因是：

- 厂商驱动体积较大
- 你已经在 `other/2D激光雷达资料/` 里有完整资料
- 本仓库更适合保留可维护的封装层，而不是把第三方源码直接散进来

## 推荐目录

```text
robot-ros/
├─ src/
│  ├─ lslidar_driver/          # 厂商驱动，建议用导入脚本拷贝进来
│  ├─ lslidar_msgs/            # 厂商消息包，建议用导入脚本拷贝进来
│  ├─ sparkrobot_bringup/
│  ├─ sparkrobot_dog_bridge/
│  └─ sparkrobot_nav_bridge/
```

## 导入厂商驱动

在 `repos/robot-onboard/` 下执行：

```bash
python tools/scripts/robot/import_lslidar_driver.py
```

该脚本会从你当前仓库里的本地资料目录复制：

- `lslidar_driver`
- `lslidar_msgs`

到 `robot-ros/src/`。

## 构建

在目标 Linux 设备上执行：

```bash
cd robot-ros
colcon build --symlink-install
```

## 常用启动命令

```bash
source install/setup.bash
ros2 launch sparkrobot_bringup bringup.launch.py
ros2 launch sparkrobot_bringup mapping.launch.py
ros2 launch sparkrobot_bringup localization.launch.py
ros2 launch sparkrobot_bringup navigation.launch.py
```

## 说明

- 默认正式部署优先走网口版 N10P
- 串口版参数模板已保留，适合台架调试和应急备份
- `nav2.yaml` 目前是可启动的初始骨架，后续还需要按机器狗运动学和避障效果继续整定
- `sparkrobot_nav_bridge` 当前已支持通过本地 Unix Socket 把单点导航目标转发给 Nav2 `navigate_to_pose`
- `sparkrobot_dog_bridge` 当前已支持：
  - 订阅 `/cmd_vel` 并通过现有 SDK 连续下发速度
  - 通过 `robot-server` 的完整遥测接口发布 `/imu`、`/odom`
  - 发布 `odom -> base_link` TF
  - 发布 `/sparkrobot/bridge_status`
  - 通过 UDP 把 `bridge_status` 回灌到 `robot-server /api/v1/telemetry/full`
- 如果在 WSL 中运行，由于没有 SDK 和真机遥测，`sparkrobot_dog_bridge` 会退化为“节点可启动，但不真正控狗”
