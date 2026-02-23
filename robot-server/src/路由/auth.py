"""
认证路由 - 处理登录、登出和会话验证
"""
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from ..服务.auth_service import 获取认证服务单例

router = APIRouter()
auth_service = 获取认证服务单例()


@router.post("/api/v1/auth/login")
async def 登录(request: Request, response: Response) -> dict:
    """用户登录"""
    try:
        data = await request.json()
        username = data.get("username", "")
        password = data.get("password", "")

        if not username or not password:
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": "用户名和密码不能为空"}
            )

        token = auth_service.login(username, password)

        if token:
            # 设置cookie（HttpOnly, SameSite等安全选项）
            response.set_cookie(
                key="session_token",
                value=token,
                httponly=True,
                max_age=3600,  # 1小时
                samesite="lax"
            )
            return {
                "success": True,
                "message": "登录成功",
                "token": token
            }
        else:
            raise HTTPException(
                status_code=401,
                detail={"success": False, "error": "用户名或密码错误"}
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.post("/api/v1/auth/logout")
async def 登出(
    response: Response,
    session_token: Optional[str] = Cookie(None)
) -> dict:
    """用户登出"""
    try:
        if session_token:
            auth_service.logout(session_token)

        # 清除cookie
        response.delete_cookie(key="session_token")

        return {
            "success": True,
            "message": "登出成功"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.get("/api/v1/auth/status")
async def 检查登录状态(
    session_token: Optional[str] = Cookie(None)
) -> dict:
    """检查当前登录状态"""
    try:
        is_logged_in = auth_service.validate_token(session_token)
        username = None
        if is_logged_in and session_token:
            username = auth_service.get_username(session_token)

        return {
            "success": True,
            "logged_in": is_logged_in,
            "username": username
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e


@router.get("/api/v1/auth/check")
async def 验证Token(
    session_token: Optional[str] = Cookie(None)
) -> dict:
    """验证token是否有效（用于前端检查）"""
    try:
        valid = auth_service.validate_token(session_token)
        return {
            "success": True,
            "valid": valid
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        ) from e
