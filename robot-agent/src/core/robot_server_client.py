from pathlib import Path
from typing import Any

import httpx
from sparkrobot_common import 获取项目版本

from src.core.auth_client import get_auth_client


class RobotServerClient:
    """负责访问本地 robot-server HTTP API。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8080") -> None:
        self.base_url = base_url.rstrip("/")

    def _获取认证cookies(self) -> dict[str, str]:
        """获取认证 cookies。"""
        token = get_auth_client().获取_token()
        return {"session_token": token} if token else {}

    def _构建URL(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"

    async def 调用API(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """调用 robot-server HTTP API。"""
        cookies = self._获取认证cookies()
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(self._构建URL(path), cookies=cookies, timeout=10.0)
            else:
                response = await client.post(self._构建URL(path), json=payload, cookies=cookies, timeout=10.0)
        result = response.json()
        return result if isinstance(result, dict) else {}

    def 获取版本(self, fallback_project_dir: Path) -> str:
        """获取本地 robot-server 版本号，优先 HTTP API，失败后读取包版本。"""
        try:
            cookies = self._获取认证cookies()
            with httpx.Client(timeout=2.0) as client:
                response = client.get(self._构建URL("/api/v1/system/info"), cookies=cookies)
                if response.status_code == 200:
                    payload = response.json()
                    info = payload.get("info", {}) if isinstance(payload, dict) else {}
                    version = info.get("robot_server_version")
                    if isinstance(version, str) and version.strip():
                        return version.strip()
        except Exception:
            pass

        return 获取项目版本(fallback_project_dir, "robot-server", "unknown")
