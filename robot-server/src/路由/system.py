from fastapi import APIRouter, HTTPException
from sparkrobot_common import CONFIG_DIR

from .. import __version__ as ROBOT_SERVER_VERSION
from ..服务.config_service import 获取配置管理器单例

router = APIRouter()
config_manager = 获取配置管理器单例()


@router.get("/api/v1/system/info")
async def 获取系统信息():
    try:
        info = {
            "config_dir": str(CONFIG_DIR),
            "config_file": str(config_manager.config_path),
            "robot_server_version": ROBOT_SERVER_VERSION,
        }
        return {"success": True, "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e
