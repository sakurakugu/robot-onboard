import asyncio
from typing import Any

from sparkrobot_common import (
    获取运行时IPC路径,
    get_logger,
    构建运行时事件,
    构建运行时成功响应,
    构建运行时错误响应,
    编码运行时消息,
    解码运行时消息,
    运行时状态事件名,
)

from src.services import 导航目标, 运行时控制服务, 运行时状态服务

logger = get_logger("robot-runtime")


class 运行时IPC服务器:
    """本地运行时 IPC/RPC 服务。"""

    def __init__(self, project_name: str, 状态服务: 运行时状态服务, 控制服务: 运行时控制服务) -> None:
        self.project_name = project_name
        self.状态服务 = 状态服务
        self.控制服务 = 控制服务
        self._server: asyncio.AbstractServer | None = None

    async def 启动(self) -> None:
        """启动 IPC 服务。"""
        ipc_path = 获取运行时IPC路径(self.project_name)
        try:
            if ipc_path.exists():
                ipc_path.unlink()
        except Exception:
            pass

        self._server = await asyncio.start_unix_server(self._处理连接, path=str(ipc_path))  # type: ignore[attr-defined]
        logger.info("运行时 IPC 服务启动: %s", ipc_path)

    async def 关闭(self) -> None:
        """关闭 IPC 服务。"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        try:
            ipc_path = 获取运行时IPC路径(self.project_name)
            if ipc_path.exists():
                ipc_path.unlink()
        except Exception:
            pass

    async def _处理连接(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logger.debug("运行时 IPC 新连接: %s", peer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                request_id = "unknown"
                try:
                    message = 解码运行时消息(line)
                    request_id = str(message.get("id") or "unknown")
                    should_close = await self._处理消息(message, writer)
                    if should_close:
                        break
                except Exception as exc:
                    logger.warning("处理 IPC 请求失败: %s", exc)
                    await self._发送消息(
                        writer,
                        构建运行时错误响应(
                            request_id,
                            "invalid_request",
                            f"非法请求: {exc}",
                        ),
                    )
        except Exception as exc:
            logger.warning("IPC 连接异常: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _处理消息(self, message: dict[str, Any], writer: asyncio.StreamWriter) -> bool:
        """处理单条请求消息。"""
        request_type = str(message.get("type", ""))
        request_id = str(message.get("id") or "unknown")
        if request_type != "request":
            await self._发送消息(
                writer,
                构建运行时错误响应(request_id, "invalid_message_type", "仅支持 request 类型消息"),
            )
            return False

        method = str(message.get("method") or "").strip()
        params = message.get("params", {})
        if not isinstance(params, dict):
            await self._发送消息(
                writer,
                构建运行时错误响应(request_id, "invalid_params", "params 必须是对象"),
            )
            return False

        if method == "runtime.subscribe_state":
            await self._发送状态订阅响应(request_id, params, writer)
            return True

        response = await self._执行请求(request_id, method, params)
        await self._发送消息(writer, response)
        return False

    async def _执行请求(self, request_id: str, method: str, params: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
        """执行 RPC 方法。"""
        try:
            if method == "runtime.ping":
                return 构建运行时成功响应(
                    request_id,
                    {
                        "ok": True,
                        "project": self.project_name,
                    },
                )

            if method == "runtime.get_summary":
                return 构建运行时成功响应(request_id, self.状态服务.构建摘要())

            if method == "runtime.get_state":
                return 构建运行时成功响应(request_id, self.状态服务.获取完整状态())

            if method == "lidar.get_scan":
                return 构建运行时成功响应(request_id, await self.控制服务.获取激光扫描())

            if method == "mapping.get_preview":
                return 构建运行时成功响应(request_id, await self.控制服务.获取地图预览())

            if method == "manual.start_session":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.开始手动控制(
                        模式=self._可选字符串(params, "mode") or "move",
                        来源=self._可选字符串(params, "source") or "runtime",
                        session_id=self._可选字符串(params, "session_id"),
                    ),
                )

            if method == "manual.update_velocity":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.更新手动速度(
                        模式=self._可选字符串(params, "mode") or "move",
                        vx=self._浮点值(params, "vx"),
                        vy=self._解析可选浮点(params.get("vy")) or 0.0,
                        wz=self._解析可选浮点(params.get("wz")) or 0.0,
                        来源=self._可选字符串(params, "source") or "runtime",
                        session_id=self._可选字符串(params, "session_id"),
                    ),
                )

            if method == "manual.stop":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.停止手动控制(self._可选字符串(params, "session_id")),
                )

            if method == "direct_control.execute":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.执行直连控制(
                        payload=self._可选字典(params, "payload") or {},
                        来源=self._可选字符串(params, "source") or "runtime",
                    ),
                )

            if method == "sdk_mode.set":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.切换SDK模式(
                        enabled=self._可选布尔值(params, "enabled"),
                        来源=self._可选字符串(params, "source") or "runtime",
                    ),
                )

            if method == "manual.estop":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.立即急停(
                        来源=self._可选字符串(params, "source") or "runtime",
                    ),
                )

            if method == "action.execute":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.执行动作(
                        action_name=self._必填字符串(params, "action_name"),
                        parameters=self._可选字典(params, "parameters"),
                        来源=self._可选字符串(params, "source") or "runtime",
                        action_id=self._可选字符串(params, "action_id"),
                    ),
                )

            if method == "action.cancel":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.取消动作(self._可选字符串(params, "action_id")),
                )

            if method == "mapping.start":
                return self._转换控制结果(request_id, await self.控制服务.开始建图(self._可选字符串(params, "map_name")))

            if method == "mapping.stop":
                return self._转换控制结果(request_id, await self.控制服务.停止建图(self._可选布尔值(params, "save_map")))

            if method == "mapping.load":
                map_name = self._必填字符串(params, "map_name")
                return self._转换控制结果(request_id, await self.控制服务.加载地图(map_name))

            if method == "localization.start":
                return self._转换控制结果(request_id, await self.控制服务.开始定位(self._可选字符串(params, "map_name")))

            if method == "localization.stop":
                return self._转换控制结果(request_id, await self.控制服务.停止定位())

            if method == "localization.set_initial_pose":
                return self._转换控制结果(
                    request_id,
                    await self.控制服务.设置初始位姿(
                        x=self._浮点值(params, "x"),
                        y=self._浮点值(params, "y"),
                        yaw=self._浮点值(params, "yaw"),
                        frame_id=self._可选字符串(params, "frame_id") or "map",
                        地图名称=self._可选字符串(params, "map_name"),
                    ),
                )

            if method == "navigation.navigate_to":
                goal = 导航目标(
                    x=self._浮点值(params, "x"),
                    y=self._浮点值(params, "y"),
                    yaw=self._浮点值(params, "yaw"),
                    frame_id=self._可选字符串(params, "frame_id") or "map",
                    地图名称=self._可选字符串(params, "map_name"),
                    目标ID=self._可选字符串(params, "goal_id"),
                )
                return self._转换控制结果(request_id, await self.控制服务.导航到目标(goal))

            if method == "navigation.cancel":
                return self._转换控制结果(request_id, await self.控制服务.取消导航())

            if method == "patrol.start":
                task_name = self._必填字符串(params, "task_name")
                waypoint_file = self._必填字符串(params, "waypoint_file")
                return self._转换控制结果(request_id, await self.控制服务.开始巡逻(task_name, waypoint_file))

            if method == "task.pause":
                return self._转换控制结果(request_id, await self.控制服务.暂停当前任务())

            if method == "task.resume":
                return self._转换控制结果(request_id, await self.控制服务.恢复当前任务())

            if method == "task.terminate":
                return self._转换控制结果(request_id, await self.控制服务.终止当前任务())

            return 构建运行时错误响应(
                request_id,
                "method_not_found",
                f"未支持的方法: {method}",
            )
        except ValueError as exc:
            return 构建运行时错误响应(
                request_id,
                "invalid_params",
                str(exc),
            )
        except Exception as exc:
            logger.exception("执行 IPC 方法失败: method=%s", method)
            return 构建运行时错误响应(
                request_id,
                "internal_error",
                f"运行时内部错误: {exc}",
            )

    async def _发送状态订阅响应(self, request_id: str, params: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        """处理状态订阅请求。"""
        mode = self._解析订阅模式(params.get("mode"))
        interval_sec = self._解析订阅间隔(params.get("interval_sec"))
        await self._发送消息(
            writer,
            构建运行时成功响应(
                request_id,
                {
                    "subscribed": True,
                    "mode": mode,
                    "interval_sec": interval_sec,
                },
            ),
        )
        await self._状态订阅循环(writer, mode, interval_sec)

    async def _状态订阅循环(self, writer: asyncio.StreamWriter, mode: str, interval_sec: float) -> None:
        """持续推送状态事件。"""
        while not writer.is_closing():
            if mode == "full":
                payload = self.状态服务.获取完整状态()
            else:
                payload = self.状态服务.构建摘要()

            await self._发送消息(
                writer,
                构建运行时事件(
                    运行时状态事件名,
                    {
                        "mode": mode,
                        "payload": payload,
                    },
                ),
            )
            await asyncio.sleep(interval_sec)

    async def _发送消息(self, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        """发送单条消息。"""
        writer.write(编码运行时消息(message))
        await writer.drain()

    def _转换控制结果(self, request_id: str, result: Any) -> dict[str, Any]:
        """把控制服务结果转换为协议响应。"""
        payload = result.导出字典()
        if result.成功:
            return 构建运行时成功响应(request_id, payload)
        return 构建运行时错误响应(
            request_id,
            result.错误码 or "runtime_command_failed",
            result.消息,
            payload.get("data", {}),
        )

    def _必填字符串(self, params: dict[str, Any], key: str) -> str:
        value = self._可选字符串(params, key)
        if not value:
            raise ValueError(f"缺少必要参数: {key}")
        return value

    def _可选字符串(self, params: dict[str, Any], key: str) -> str | None:
        value = params.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _浮点值(self, params: dict[str, Any], key: str) -> float:
        value = params.get(key)
        if value is None:
            raise ValueError(f"缺少必要参数: {key}")
        return float(value)

    def _可选布尔值(self, params: dict[str, Any], key: str) -> bool | None:
        value = params.get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        return bool(value)

    def _可选字典(self, params: dict[str, Any], key: str) -> dict[str, Any] | None:
        value = params.get(key)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"{key} 必须是对象")
        return value

    def _解析可选浮点(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError("浮点参数格式不正确") from None

    def _解析订阅模式(self, value: Any) -> str:
        mode = str(value or "summary").strip().lower()
        if mode not in {"summary", "full"}:
            return "summary"
        return mode

    def _解析订阅间隔(self, value: Any) -> float:
        try:
            interval = float(value if value is not None else 1.0)
        except (TypeError, ValueError):
            interval = 1.0
        return max(0.2, min(interval, 10.0))
