from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..依赖 import 需要认证
from ..服务.log_service import 获取日志服务单例

router = APIRouter()
log_service = 获取日志服务单例()


@router.get("/api/v1/logs")
async def 获取日志列表(app_name: str | None = Query(default=None, description="按应用名筛选")) -> dict:
    try:
        logs, apps, _ = log_service.获取日志列表(app_name=app_name)
        return {"success": True, "apps": apps, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.get("/api/v1/logs/download")
async def 打包下载日志(
    start_time: datetime = Query(..., description="开始时间，ISO8601格式"),
    end_time: datetime = Query(..., description="结束时间，ISO8601格式"),
    app_name: str | None = Query(default=None, description="按应用名筛选"),
    _token: str = Depends(需要认证),
) -> Response:
    try:
        zip_data, file_name = log_service.打包下载(
            start_time=start_time,
            end_time=end_time,
            app_name=app_name,
        )
        encoded_file_name = quote(file_name)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_file_name}"
        }
        return Response(content=zip_data, media_type="application/zip", headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)}) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"success": False, "error": str(e)}) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e
