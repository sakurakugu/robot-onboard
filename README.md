# robot-onboard

机器狗本体端仓库，负责本地配置、遥测、运行时、ROS 和远程安装打包。

## 目录结构

```text
robot-onboard/
├── robot-agent/             # 对外通信代理
├── robot-server/            # 本地 FastAPI 配置与遥测服务
├── robot-runtime/           # 本体运行时内核
├── robot-ros/               # ROS2 工作空间
├── sparkrobot-common/       # 公共库
├── tools/                   # 打包、安装、联调脚本
├── docs/                    # 本体专项文档
├── examples/                # 示例与实验代码
└── README.md
```

## 当前职责

- `robot-server`：提供 `8080` 本地 HTTP 配置、日志、WiFi、音量、SDK、遥测接口
- `robot-agent`：连接云端、工作站、手机，承接 WebSocket、音视频和控制消息
- `robot-runtime`：聚合控制、任务、状态、地图流程
- `robot-ros`：承接激光雷达、建图、定位、导航
- `sparkrobot-common`：沉淀配置、常量、公共工具

## 环境要求

- Python `3.10+`
- Ubuntu 22.04 或 WSL Ubuntu 22.04
- ROS2 Humble

建议：

- `sparkrobot-common`、`robot-server`、`robot-agent`、`robot-runtime` 使用虚拟环境开发
- `robot-ros` 尽量沿用系统 Python + ROS 环境

## 环境注意事项

- 不要在系统 Python 上随意升级 `setuptools`
- 如果系统用户目录包污染了 ROS，可先临时设置 `PYTHONNOUSERSITE=1`
- 如果 `colcon build --symlink-install` 出现 `option --editable not recognized`，优先排查用户目录 Python 包干扰

## 常用脚本入口

```bash
python tools/1.常用命令.py
```

这个脚本主要负责：

- 本地打包
- 远程安装
- 安装目标管理
- 常用联调入口

## 常用命令

### 本地打包

```bash
python tools/1.常用命令.py --package common
python tools/1.常用命令.py --package server
python tools/1.常用命令.py --package agent
python tools/1.常用命令.py --package runtime
python tools/1.常用命令.py --package ros
python tools/1.常用命令.py --package full
```

### 远程安装

```bash
python tools/1.常用命令.py --install common --robot-ip 192.168.5.111
python tools/1.常用命令.py --install server --robot-ip 192.168.5.111
python tools/1.常用命令.py --install full --robot-ip 192.168.5.111
```

可选参数：

- `--robot-port`：目标机器狗 SSH 端口，默认 `43988`
- `--save-target`：把当前目标保存成默认安装目标
- `--format`：打包格式，支持 `tar.gz`、`zip`、`tar`、`tar.bz2`、`tar.xz`

## 现场默认远程信息

- 地址：`192.168.5.111`
- 用户名：`firefly`
- 密码：`firefly`

## 常用接口

- `robot-server`：`http://<robotIp>:8080`
- 直控 WebSocket：`ws://<robotIp>:8082`
- 本地视频 WHEP：`http://<robotIp>:8889/test/whep`

## 校验

Python 子项目修改后，至少执行对应目录的：

```bash
ruff check
mypy
```

如果改动了 `robot-ros`，还需要在 ROS 环境下补充构建验证。

## 建议优先阅读的文档

- `docs/1. 连接机器狗.md`
- `docs/3. 2D激光雷达与导航重构蓝图.md`
- `docs/4. ROS2联调与WSL验证步骤.md`
- `docs/5. WSL Ubuntu 22.04 rosdep update 失败排查.md`
- `docs/6. 本体一键打包与安装说明.md`
- `docs/7. N10P网口版现场联调记录.md`

父仓库补充资料位于：

- `robot-system/docs/`
- `robot-system/other/`
