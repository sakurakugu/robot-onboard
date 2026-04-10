# sparkrobot_dog_bridge

当前已实现的能力：

- 订阅 `/cmd_vel`
- 通过现有智元 Python SDK 调用 `move(vx, vy, yaw_rate)`
- 轮询 `robot-server` 的 `/api/v1/telemetry/full`
- 当速度指令超时、遥测离线或急停激活时自动输出零速度
- 对 `cmd_vel` 输出做基础加速度限幅
- 在低线速度、小角速度切换场景下支持基础原地转向策略
- 发布：
  - `/imu`
  - `/odom`
  - `odom -> base_link` TF
  - `/sparkrobot/dog_state`
  - `/sparkrobot/feedback`
  - `/sparkrobot/navigation_state`
  - `/sparkrobot/bridge_status`

常用参数：

- `command_timeout_sec`：超过该时间未收到新 `cmd_vel` 时自动停车，默认 `0.5`
- `telemetry_offline_timeout_sec`：遥测多久未刷新判定为离线，默认 `1.5`
- `stop_on_telemetry_offline`：遥测离线时是否强制停车，默认 `true`
- `emergency_stop_topic`：急停话题，默认 `/sparkrobot/emergency_stop`
- `auto_stand_up_on_startup`：SDK 初始化后是否自动执行一次站立，默认 `false`
- `stand_up_wait_sec`：自动站立后等待机体进入可运动状态的秒数，默认 `3.0`
- `max_linear_x / max_linear_y / max_angular_z`：基础速度上限
- `max_accel_x / max_accel_y / max_accel_z`：基础加速度限幅
- `rotate_in_place_enabled`：是否启用原地转向策略，默认 `true`
- `rotate_in_place_angular_threshold`：判定为原地转向的角速度阈值
- `rotate_in_place_linear_deadband`：原地转向时允许的线速度死区
- `bridge_status_topic`：桥接运行状态话题，默认 `/sparkrobot/bridge_status`
- `status_hz`：桥接状态发布频率，默认 `5.0`
- `report_bridge_status_to_server`：是否把桥接状态回灌到 `robot-server`，默认 `true`
- `telemetry_udp_host / telemetry_udp_port`：桥接状态回灌目标，默认 `127.0.0.1:8080/udp`

`/sparkrobot/bridge_status` 当前会给出这些调试字段：

- `telemetry_online`
- `telemetry_motion_ready`
- `telemetry_last_success_age_sec`
- `command_age_sec`
- `emergency_stop`
- `arbitration_reason`
- `target_velocity`
- `output_velocity`

如果 `report_bridge_status_to_server=true`，那么 `robot-server` 的：

- `GET /api/v1/telemetry/full`

里也会出现：

- `bridge_status`

联调建议：

- 真机 Ubuntu 上优先验证真实控狗
- WSL 中优先验证节点是否启动、topic/TF 是否存在、参数是否生效
- 急停可直接发布 `std_msgs/Bool` 到 `/sparkrobot/emergency_stop`
- 如果首次下发 `cmd_vel` 前机体还没进入可运动姿态，优先开启 `auto_stand_up_on_startup=true`

当前约束：

- 速度控制仍然基于 `move(vx, vy, yaw_rate)`，还没有接 gait、姿态或更高层运控仲裁
- 暂停 / 恢复还没有和任务层做统一速度仲裁
- 遥测目前依赖 `robot-server` 后台服务已启动
- 在 WSL 中通常只能验证节点启动和话题结构，不能真正控狗
