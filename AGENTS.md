## 项目概览

机器狗本体仓库，包含以下子项目：

| 目录 | 技术栈 | 说明 |
| --- | --- | --- |
| `robot-agent/` | Python 3.10+ | 机器狗本体代理程序 |
| `robot-server/` | Python 3.10+ + FastAPI | 机器狗本地配置服务 |
| `sparkrobot-common/` | Python 3.10+ | 公共库 |
| `tools/` | Python | 打包、安装、测试脚本 |

---

## 约定

- Python 使用 mypy 和 ruff
- 所有注释一律使用中文，回复也使用中文
- 如需安装库，直接安装
- 该项目为自用项目，可以重构不用向前兼容
