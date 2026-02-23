"""SDK 配置路由模块 - 提供 SDK 配置和运控管理的 API 接口

API 端点：
- GET /api/v1/sdk/config - 查看 SDK 配置
- POST /api/v1/sdk/config - 修改 SDK 配置
- POST /api/v1/sdk/config/reset - 重置 SDK 配置
- GET /api/v1/sdk/motion - 查看运控配置
- POST /api/v1/sdk/motion - 修改运控配置
- POST /api/v1/sdk/motion/reset - 重置运控配置
- POST /api/v1/sdk/motion/restart - 重启运控服务
"""

from fastapi import APIRouter, HTTPException, Request

from ..服务 import sdk_service

router = APIRouter()


# ==================== SDK 配置相关 ====================

@router.get("/api/v1/sdk/config")
async def 获取SDK配置() -> dict:
    """查看当前 SDK 配置"""
    try:
        success, config, error = sdk_service.查看SDK配置()
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "config": config
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/sdk/config")
async def 修改SDK配置(request: Request) -> dict:
    """修改 SDK 配置"""
    try:
        data = await request.json()
        target_ip = data.get("target_ip")
        target_port = data.get("target_port")

        if not target_ip or not target_port:
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": "缺少必要参数 target_ip 或 target_port"}
            )

        # 验证 IP 格式
        import re
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target_ip):
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": "IP 地址格式无效"}
            )

        # 验证端口范围
        try:
            port = int(target_port)
            if not (1 <= port <= 65535):
                raise ValueError
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": "端口号必须在 1-65535 之间"}
            ) from None

        success, error = sdk_service.修改SDK配置(target_ip, port)
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "message": f"SDK 配置已更新 (target_ip: {target_ip}, target_port: {port})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/sdk/config/reset")
async def 重置SDK配置() -> dict:
    """重置 SDK 配置为默认值"""
    try:
        success, error = sdk_service.重置SDK配置()
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "message": "SDK 配置已重置为默认值 (127.0.0.1:43988)"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


# ==================== 运控配置相关 ====================

@router.get("/api/v1/sdk/motion")
async def 获取运控配置() -> dict:
    """查看当前运控配置"""
    try:
        success, config, error = sdk_service.查看运控配置()
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "config": config
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/sdk/motion")
async def 修改运控配置(request: Request) -> dict:
    """修改运控配置"""
    try:
        data = await request.json()
        sdk_client_ip = data.get("sdk_client_ip")

        # 如果提供了 IP，验证格式
        if sdk_client_ip and sdk_client_ip.strip():
            import re
            if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", sdk_client_ip):
                raise HTTPException(
                    status_code=400,
                    detail={"success": False, "error": "IP 地址格式无效"}
                )
        else:
            # 空值表示清除配置
            sdk_client_ip = None

        success, error = sdk_service.修改运控配置(sdk_client_ip)
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        message = f"运控配置已更新 (SDK_CLIENT_IP: {sdk_client_ip})" if sdk_client_ip else "运控配置已更新（已清除 SDK_CLIENT_IP）"
        return {
            "success": True,
            "message": message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/sdk/motion/reset")
async def 重置运控配置() -> dict:
    """重置运控配置（清除 SDK_CLIENT_IP）"""
    try:
        success, error = sdk_service.重置运控配置()
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "message": "运控配置已重置（已清除 SDK_CLIENT_IP）"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


# ==================== 运控服务管理 ====================

@router.post("/api/v1/sdk/motion/restart")
async def 重启运控服务() -> dict:
    """重启运控服务

    注意：重启前请确保机器狗已经卧倒，否则会急停！
    """
    try:
        success, error = sdk_service.重启运控服务()
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"success": False, "error": error}
            )

        return {
            "success": True,
            "message": "运控服务重启成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e
