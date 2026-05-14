# robot-onboard

机器狗本体相关代码仓库，包含：

- `robot-agent`：运行在机器狗上的代理程序
- `robot-ros`：ROS2 工作空间，负责雷达驱动、建图、定位与导航启动
- `robot-runtime`：本体运行时内核，负责统一状态、导航任务与本地桥接
- `robot-server`：运行在机器狗上的本地配置服务
- `sparkrobot-common`：两者共享的公共库
- `tools`：打包、安装、联机测试脚本

- 一些参考文档在根目录 `robot-system` 的 `other/` 目录下

## 常用目录

- `robot-agent/`
- `robot-ros/`
- `robot-runtime/`
- `robot-server/`
- `sparkrobot-common/`
- `tools/`
- `docs/`
- `examples/`

## 打包产物

机器人安装包默认输出到 `dist/packages/`。

## 环境注意事项

- `robot-ros/` 基于 ROS Humble，构建时不要在系统 Python 上随意执行 `pip install --user --upgrade setuptools` 这类命令
- 如果系统 Python 的用户目录里装了过新的 `setuptools`，可能导致 `colcon build --symlink-install` 失败，报 `error: option --editable not recognized`
- 本地开发 `sparkrobot-common`、`robot-server`、`robot-agent` 时，优先使用虚拟环境；ROS 工作空间仍建议使用系统 Python + ROS 自带环境
- 如果怀疑用户目录 Python 包干扰了 ROS，可先临时执行 `export PYTHONNOUSERSITE=1`

## 2D 激光雷达相关

N10P 的 ROS2 驱动工作空间位于 `robot-ros/`。

如果需要把本地资料包中的厂商驱动导入到工作空间，可运行：

```bash
python tools/scripts/robot/import_lslidar_driver.py
```

建议先读的文档：

- `docs/3. 2D激光雷达与导航重构蓝图.md`
- `docs/8. 本体控制架构收敛建议.md`
- `docs/4. ROS2联调与WSL验证步骤.md`
- `docs/5. WSL Ubuntu 22.04 rosdep update 失败排查.md`

> 一些文档在父仓库的 other/ 目录下，路径为 `robot-system/other/`
