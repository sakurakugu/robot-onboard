from typing import Any

from fastapi import APIRouter, HTTPException

from ..服务 import runtime_service

router = APIRouter()


@router.get("/api/v1/runtime/ping")
async def 获取运行时探活() -> dict[str, Any]:
    """获取运行时探活结果。"""
    data = await runtime_service.获取运行时探活结果()
    return {"success": True, "data": data}


@router.get("/api/v1/runtime/summary")
async def 获取运行时状态摘要() -> dict[str, Any]:
    """获取运行时状态摘要。"""
    try:
        data = await runtime_service.获取运行时摘要()
        return {"success": True, "data": data}
    except Exception as exc:
        error = runtime_service.格式化运行时异常(exc)
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": error["message"],
                "error_code": error["code"],
                "details": error["details"],
            },
        ) from exc


@router.get("/api/v1/runtime/state")
async def 获取运行时完整状态() -> dict[str, Any]:
    """获取运行时完整状态。"""
    try:
        data = await runtime_service.获取运行时完整状态()
        return {"success": True, "data": data}
    except Exception as exc:
        error = runtime_service.格式化运行时异常(exc)
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": error["message"],
                "error_code": error["code"],
                "details": error["details"],
            },
        ) from exc
