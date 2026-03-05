"""
音量控制路由 - 提供音量获取和设置的 API
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..服务.volume_service import 获取音量服务单例
from ..认证 import 需要认证

router = APIRouter()
volume_service = 获取音量服务单例()


class VolumeSetRequest(BaseModel):
    """设置音量请求"""
    volume: int = Field(..., ge=0, le=100, description="音量值 (0-100)")


class MuteSetRequest(BaseModel):
    """设置静音请求"""
    mute: bool = Field(..., description="静音状态")


@router.get("/api/v1/volume")
async def 获取音量() -> dict:
    """
    获取当前系统音量信息

    Returns:
        {
            "success": true,
            "data": {
                "volume": 50,  // 音量 0-100
                "muted": false  // 是否静音
            }
        }
    """
    try:
        info = volume_service.获取音量信息()
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/volume")
async def 设置音量(request: VolumeSetRequest, _token: str = Depends(需要认证)) -> dict:
    """
    设置系统音量

    Args:
        request: 包含音量值的请求体

    Returns:
        {
            "success": true,
            "message": "音量已设置为 50"
        }
    """
    try:
        volume_service.设置音量(request.volume)
        return {
            "success": True,
            "message": f"音量已设置为 {request.volume}",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": str(e)}
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/volume/mute")
async def 设置静音(request: MuteSetRequest, _token: str = Depends(需要认证)) -> dict:
    """
    设置静音状态

    Args:
        request: 包含静音状态的请求体

    Returns:
        {
            "success": true,
            "message": "已静音"
        }
    """
    try:
        volume_service.设置静音(request.mute)
        message = "已静音" if request.mute else "已取消静音"
        return {
            "success": True,
            "message": message,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e
