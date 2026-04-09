这里存放 `tools/` 目录下各类辅助脚本会复用的 Python 模块和小工具。

当前和 2D 激光雷达相关的脚本：

- `robot/import_lslidar_driver.py`

用途：

- 从本地资料目录导入 `lslidar_driver`
- 从本地资料目录导入 `lslidar_msgs`
- 覆盖写入 `robot-ros/src/` 下的同名目录，方便重复同步厂商版本

默认用法：

```bash
cd repos/robot-onboard
python tools/scripts/robot/import_lslidar_driver.py
```

如果资料目录或工作空间目录不同，也可以显式指定：

```bash
python tools/scripts/robot/import_lslidar_driver.py \
  --source-dir "D:\path\to\LSLIDAR_X_ROS2\src" \
  --workspace-dir "D:\path\to\robot-ros"
```

导入完成后，下一步通常是在 `robot-ros/` 里执行：

```bash
colcon build --symlink-install
```
