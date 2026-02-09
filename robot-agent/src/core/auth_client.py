"""
认证客户端 - 负责与 robot-server 的认证交互

功能：
1. 从配置读取用户名和密码
2. 自动登录获取 token
3. 缓存 token 并在请求时附加
4. token 过期自动重新登录
"""
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from sparkrobot_common import ROBOT_SERVER_URL


class AuthClient:
    """认证客户端 - 单例模式"""

    _instance: Optional["AuthClient"] = None
    _lock = threading.Lock()

    def __init__(self, server_url: str = ROBOT_SERVER_URL):
        """初始化认证客户端

        Args:
            server_url: robot-server 地址
        """
        self.server_url = server_url
        self._token: Optional[str] = None
        self._token_time: float = 0
        self._username: str = ""
        self._password: str = ""
        self._session_timeout: int = 3600  # 默认 1 小时

    @classmethod
    def get_instance(cls, server_url: str = ROBOT_SERVER_URL) -> "AuthClient":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(server_url)
        return cls._instance

    def configure(self, username: str, password: str, session_timeout: int = 3600) -> None:
        """配置认证信息

        Args:
            username: 用户名
            password: 密码
            session_timeout: 会话超时时间（秒）
        """
        self._username = username
        self._password = password
        self._session_timeout = session_timeout

    def _is_token_expired(self) -> bool:
        """检查 token 是否过期"""
        if not self._token:
            return True
        # 提前 60 秒刷新，避免边界情况
        return time.time() - self._token_time > (self._session_timeout - 60)

    def _login(self) -> bool:
        """执行登录操作

        Returns:
            是否登录成功
        """
        if not self._username or not self._password:
            print("[AuthClient] 未配置认证信息，无法登录")
            return False

        api_url = f"{self.server_url}/api/v1/auth/login"

        try:
            data = json.dumps({
                "username": self._username,
                "password": self._password
            }).encode("utf-8")

            req = urllib.request.Request(api_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))

                if result.get("success") and "token" in result:
                    self._token = result["token"]
                    self._token_time = time.time()
                    print(f"[AuthClient] 登录成功，用户: {self._username}")
                    return True
                else:
                    print(f"[AuthClient] 登录失败: {result.get('error', '未知错误')}")
                    return False

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[AuthClient] 登录请求失败 (HTTP {e.code}): {error_msg}")
            return False
        except Exception as e:
            print(f"[AuthClient] 登录时出错: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """获取有效的认证 token

        如果 token 不存在或已过期，会自动尝试登录

        Returns:
            认证 token，如果获取失败返回 None
        """
        if self._is_token_expired():
            if not self._login():
                return None

        return self._token

    def add_auth_to_request(self, req: urllib.request.Request) -> bool:
        """为请求添加认证信息

        Args:
            req: urllib.request.Request 对象

        Returns:
            是否成功添加认证信息
        """
        token = self.get_token()
        if not token:
            return False

        # 使用 Cookie 方式传递 token（与 robot-server 的验证方式一致）
        req.add_header("Cookie", f"session_token={token}")
        return True

    def logout(self) -> bool:
        """登出，清除本地 token

        Returns:
            是否登出成功
        """
        if not self._token:
            return True

        api_url = f"{self.server_url}/api/v1/auth/logout"

        try:
            req = urllib.request.Request(api_url, method="POST")
            req.add_header("Cookie", f"session_token={self._token}")

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                self._token = None
                self._token_time = 0
                print("[AuthClient] 登出成功")
                return result.get("success", False)

        except Exception as e:
            print(f"[AuthClient] 登出时出错: {e}")
            # 即使登出失败也清除本地 token
            self._token = None
            self._token_time = 0
            return False


# 全局实例获取函数
def get_auth_client(server_url: str = ROBOT_SERVER_URL) -> AuthClient:
    """获取认证客户端单例

    Args:
        server_url: robot-server 地址

    Returns:
        AuthClient 实例
    """
    return AuthClient.get_instance(server_url)
