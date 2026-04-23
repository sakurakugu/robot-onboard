import atexit
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .服务 import telemetry_service as 遥测服务
from .服务.config_service import 获取配置管理器单例
from .服务.mdns_service import 初始化并启动_mDNS_服务
from .路由 import auth as 认证路由
from .路由 import config as 配置路由
from .路由 import logs as 日志路由
from .路由 import maps as 地图路由
from .路由 import packages as 软件包路由
from .路由 import runtime as 运行时路由
from .路由 import sdk as SDK路由
from .路由 import system as 系统路由
from .路由 import telemetry as 遥测路由
from .路由 import volume as 音量路由
from .路由 import wifi as 无线路由

PORT = 8080

app = FastAPI(title="Robot Server", description="机器狗配置服务器")

config_manager = 获取配置管理器单例()
mdns_服务 = 初始化并启动_mDNS_服务(config_manager, PORT)
atexit.register(mdns_服务.停止)

# 启动遥测后台服务（向 dog 发心跳，缓存 dog_state）
遥测服务.start()
atexit.register(遥测服务.stop)

app.include_router(认证路由.router)
app.include_router(配置路由.router)
app.include_router(SDK路由.router)
app.include_router(遥测路由.router)
app.include_router(运行时路由.router)
app.include_router(无线路由.router)
app.include_router(系统路由.router)
app.include_router(音量路由.router)
app.include_router(日志路由.router)
app.include_router(地图路由.router)
app.include_router(软件包路由.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
