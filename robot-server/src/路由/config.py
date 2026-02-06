from fastapi import APIRouter, Depends, HTTPException, Request
from sparkrobot_common import 获取配置项字段信息

from ..依赖 import 需要认证
from ..服务.config_service import 获取配置管理器单例

router = APIRouter()
config_manager = 获取配置管理器单例()


@router.get("/api/v1/config")
async def 获取全部配置() -> dict:
    try:
        config = config_manager.获取()
        return {"success": True, "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.get("/api/v1/config/fields")
async def 获取配置项字段() -> dict:
    try:
        fields = 获取配置项字段信息()
        return {"success": True, "fields": fields}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.get("/api/v1/config/path")
async def 获取配置文件路径() -> dict:
    try:
        return {
            "success": True,
            "config_file": str(config_manager.config_path),
            "config_dir": str(config_manager.config_dir),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.post("/api/v1/config/reset")
async def 重置配置(request: Request, _token: str = Depends(需要认证)) -> dict:
    try:
        data = await request.json() if request.headers.get("content-length", "0") != "0" else {}
        key = data.get("key")

        success = config_manager.重置(key)
        if not success:
            raise HTTPException(status_code=400, detail={"success": False, "error": f"重置失败，配置项 {key} 不存在"})

        return {"success": True, "message": "配置已重置" + (f"（{key}）" if key else "（全部）")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.post("/api/v1/config/reload")
async def 重新加载配置(_token: str = Depends(需要认证)) -> dict:
    try:
        config_manager.重新加载()
        return {"success": True, "message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.get("/api/v1/config/{key}")
async def 获取单项配置(key: str) -> dict:
    try:
        value = config_manager.获取(key)
        if value is None:
            raise HTTPException(status_code=404, detail={"success": False, "error": f"配置项 {key} 不存在"})
        return {"success": True, "key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.post("/api/v1/config")
async def 更新配置(request: Request, _token: str = Depends(需要认证)) -> dict:
    try:
        data = await request.json()

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail={"success": False, "error": "请求数据必须是JSON对象"})

        results = config_manager.批量设置(data)

        failed = [k for k, v in results.items() if not v]
        if failed:
            return {
                "success": False,
                "message": f"部分配置项更新失败: {', '.join(failed)}",
                "results": results,
            }

        return {"success": True, "message": "配置更新成功", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e
