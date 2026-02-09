"""
认证服务模块 - 负责用户登录验证和会话管理

功能：
1. 验证用户名密码
2. 生成和验证session token
3. 管理会话状态和超时
"""
import hashlib
import secrets
import time
from typing import Dict, Optional

from .config_service import 获取配置管理器单例


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}  # token -> {username, created_at}
        self.config_manager = 获取配置管理器单例()

    def _get_session_timeout(self) -> int:
        """获取会话超时时间（秒）"""
        config = self.config_manager.获取()
        return config.get("auth", {}).get("session_timeout", 3600)

    def create_session(self, username: str) -> str:
        """创建新会话，返回token"""
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "username": username,
            "created_at": time.time(),
        }
        return token

    def validate_session(self, token: Optional[str]) -> bool:
        """验证会话是否有效"""
        if not token or token not in self.sessions:
            return False

        session = self.sessions[token]
        timeout = self._get_session_timeout()

        # 检查是否超时
        if time.time() - session["created_at"] > timeout:
            del self.sessions[token]
            return False

        return True

    def get_username(self, token: str) -> Optional[str]:
        """获取token对应的用户名"""
        if token in self.sessions:
            return self.sessions[token]["username"]
        return None

    def remove_session(self, token: str) -> None:
        """删除会话（登出）"""
        if token in self.sessions:
            del self.sessions[token]

    def cleanup_expired_sessions(self) -> None:
        """清理过期会话"""
        timeout = self._get_session_timeout()
        current_time = time.time()
        expired = [
            token
            for token, session in self.sessions.items()
            if current_time - session["created_at"] > timeout
        ]
        for token in expired:
            del self.sessions[token]


class AuthService:
    """认证服务"""

    def __init__(self):
        self.config_manager = 获取配置管理器单例()
        self.session_manager = SessionManager()

    def verify_credentials(self, username: str, password: str) -> bool:
        """验证用户名和密码"""
        config = self.config_manager.获取()
        auth_config = config.get("auth", {})

        expected_username = auth_config.get("username", "sparkrobot")
        expected_password = auth_config.get("password", "sparkrobot")

        return username == expected_username and password == expected_password

    def login(self, username: str, password: str) -> Optional[str]:
        """登录，成功返回token，失败返回None"""
        if self.verify_credentials(username, password):
            # 清理过期会话
            self.session_manager.cleanup_expired_sessions()
            return self.session_manager.create_session(username)
        return None

    def validate_token(self, token: Optional[str]) -> bool:
        """验证token是否有效"""
        return self.session_manager.validate_session(token)

    def logout(self, token: str) -> None:
        """登出"""
        self.session_manager.remove_session(token)

    def get_username(self, token: str) -> Optional[str]:
        """获取token对应的用户名"""
        return self.session_manager.get_username(token)


# 单例
_auth_service_instance: Optional[AuthService] = None


def 获取认证服务单例() -> AuthService:
    """获取认证服务单例"""
    global _auth_service_instance
    if _auth_service_instance is None:
        _auth_service_instance = AuthService()
    return _auth_service_instance
