# robot-runtime

机器狗本体运行时内核。

当前阶段职责：

- 统一本体状态模型
- 聚合导航、定位、雷达等运行时状态
- 作为 `robot-agent`、`robot-server` 与后续 ROS2 导航链路之间的本地桥接层

后续会逐步承接：

- 导航任务管理
- 地图加载与保存
- 巡逻任务编排
- 本地状态事件总线

## 当前目录结构

```text
robot-runtime/
├─ src/
│  ├─ core/
│  │  ├─ config/
│  │  └─ state/
│  ├─ services/
│  └─ application.py
├─ main.py
└─ pyproject.toml
```

## 运行方式

```bash
cd robot-runtime
python main.py
```

## 当前状态

当前已完成：

- 项目骨架
- 运行时配置读取
- 统一状态模型
- 运行时状态服务
- 运行时控制服务
- 地图目录与路点目录初始化
- ROS 工作空间发现与启动计划生成
- `bringup / mapping / localization` 的真实 ROS2 进程启停编排
- ROS2 进程异常退出监控与状态回收
- `robot-runtime -> sparkrobot_nav_bridge -> Nav2 Action` 本地导航目标桥接
- 导航反馈轮询同步到运行时状态
- `patrol.start` 最小可用巡逻执行器（单地图 JSON 路线）
- 通过 `robot-server /api/v1/telemetry/full` 同步机器狗电量、姿态、里程、控制模式
- 通过 `robot-server /api/v1/telemetry/full` 同步 `bridge_status`，写入运行时 `dog_bridge / 运控桥` 状态

当前未完成：

- 多地图巡逻与断点恢复策略
- 导航暂停 / 恢复行为树控制

## 当前 IPC/RPC 草案

当前已提供基于 Unix Socket + JSON Line 的本地运行时接口。

Socket 路径规则：

- `/tmp/sparkrobot/robot-runtime.sock`

请求格式：

```json
{"type":"request","id":"xxx","method":"runtime.get_summary","params":{}}
```

响应格式：

```json
{"type":"response","id":"xxx","success":true,"result":{}}
```

支持的方法：

- `runtime.ping`
- `runtime.get_summary`
- `runtime.get_state`
- `runtime.subscribe_state`
- `mapping.start`
- `mapping.stop`
- `mapping.load`
- `localization.start`
- `localization.stop`
- `navigation.navigate_to`
- `navigation.cancel`
- `patrol.start`
- `task.pause`
- `task.resume`
- `task.terminate`

当前方法状态说明：

- `mapping.start / mapping.stop`：会真实启动和停止 ROS2 建图进程
- `localization.start / localization.stop`：会真实启动和停止 ROS2 定位进程
- `navigation.navigate_to`：会拉起导航栈，并通过本地导航桥把目标转发给 Nav2 `navigate_to_pose`
- `navigation.cancel`：会先向导航桥发送取消请求，再回收本体侧导航任务状态
- `patrol.start`：会解析 JSON 路线文件，按 waypoint 顺序逐点派发到 Nav2，并支持 `task.pause / task.resume / task.terminate`

当前巡逻文件格式：

- 顶层可以是对象：`{ name, map_name, loop, arrival_wait_sec, waypoints: [...] }`
- 也可以直接是 waypoint 数组
- waypoint 字段支持：`name / x / y / yaw / frame_id / map_name / arrival_wait_sec`
- 当前只支持单地图巡逻

样例文件：

- `../examples/patrol/lab_patrol.json`

## robot-ros 工作空间

当前运行时会默认发现同级目录下的 `robot-ros/` 工作空间，并在启动日志里输出：

- 工作空间是否存在
- `sparkrobot_bringup` 是否存在
- `sparkrobot_nav_bridge` 是否存在
- `sparkrobot_dog_bridge` 是否存在
- `lslidar_driver / lslidar_msgs` 是否已经导入
- `install/setup.bash` 是否已生成
- 推荐的 `ros2 launch` 启动命令

如果厂商驱动还没有导入，可运行：

```bash
cd repos/robot-onboard
python tools/scripts/robot/import_lslidar_driver.py
```

如果需要在 Linux / WSL 里验证 ROS2 链路，可参考：

- `../docs/4. ROS2联调与WSL验证步骤.md`
