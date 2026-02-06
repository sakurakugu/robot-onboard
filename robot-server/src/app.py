import atexit
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .服务.config_service import 获取配置管理器单例
from .服务.mdns_service import 初始化并启动_mDNS_服务
from .路由 import config as config_router
from .路由 import sdk as sdk_router
from .路由 import system as system_router
from .路由 import volume as volume_router
from .路由 import wifi as wifi_router

PORT = 8080

app = FastAPI(title="Robot Server", description="机器狗配置服务器")

config_manager = 获取配置管理器单例()
mdns_service = 初始化并启动_mDNS_服务(config_manager, PORT)
atexit.register(mdns_service.停止)

app.include_router(config_router.router)
app.include_router(sdk_router.router)
app.include_router(wifi_router.router)
app.include_router(system_router.router)
app.include_router(volume_router.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
