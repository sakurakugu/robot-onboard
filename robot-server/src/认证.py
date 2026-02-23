"""
认证依赖项 - 用于保护需要登录的接口
"""
from typing import Optional

from fastapi import Cookie, HTTPException

from .服务.auth_service import 获取认证服务单例


def 需要认证(session_token: Optional[str] = Cookie(None)) -> str:
    """
    认证依赖项 - 验证用户是否已登录

    返回有效的token，如果未登录则抛出401异常
    """
    auth_service = 获取认证服务单例()

    if not session_token or not auth_service.validate_token(session_token):
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "未登录或会话已过期，请先登录"}
        )

    return session_token  # 返回有效的token，路由可以选择使用


def 可选认证(session_token: Optional[str] = Cookie(None)) -> Optional[str]:
    """
    可选认证依赖项 - 不强制要求登录，但会验证token（如果提供）

    返回token（如果有效）或None
    """
    auth_service = 获取认证服务单例()

    if session_token and auth_service.validate_token(session_token):
        return session_token

    return None
