"""AI Cost Sentinel 代理服务"""

from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import ADMIN_TOKEN, BUDGET_MODE
from tracker.db import (
    init_db, get_stats, get_recent_calls, get_budget, setup_budget,
    export_csv, get_daily_cost, get_monthly_cost,
)
from proxy.forwarder import forward_request, ALLOWED_PREFIXES
from alerter.budget import check_and_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_admin(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not ADMIN_TOKEN:
        return True
    if creds is None or creds.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="访问被拒绝")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("AI Cost Sentinel 启动")
    yield
    logger.info("AI Cost Sentinel 关闭")


app = FastAPI(title="AI Cost Sentinel", version="0.3.0", lifespan=lifespan)


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_v1(request: Request, path: str):
    if not any(path.startswith(p) for p in ALLOWED_PREFIXES):
        return JSONResponse(status_code=404, content={"error": f"路径 /{path} 不被支持"})
    body = await request.body()
    project = request.headers.get("x-sentinel-project", "default")
    if not project.replace("-", "").isalnum():
        return JSONResponse(status_code=400, content={"error": "项目名只能包含字母、数字和横线"})

    if BUDGET_MODE == "reject":
        budget = await get_budget(project)
        daily = await get_daily_cost(project)
        monthly = await get_monthly_cost(project)
        if budget["daily_limit"] > 0 and daily >= budget["daily_limit"]:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "日预算已耗尽",
                    "daily_cost": round(daily, 4),
                    "daily_limit": budget["daily_limit"],
                    "project": project,
                },
            )
        if budget["monthly_limit"] > 0 and monthly >= budget["monthly_limit"]:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "月预算已耗尽",
                    "monthly_cost": round(monthly, 4),
                    "monthly_limit": budget["monthly_limit"],
                    "project": project,
                },
            )

    try:
        result = await forward_request(
            method=request.method,
            path=f"/{path}",
            headers=dict(request.headers),
            body=body,
            query_params=str(request.query_params) if request.query_params else "",
            project=project,
        )
    except Exception as e:
        logger.error(f"代理失败: {e}")
        return JSONResponse(status_code=502, content={"error": "代理请求失败", "details": str(e)})
    # 异步触发预算告警（不阻塞响应）
    asyncio.create_task(check_and_alert(project))

    if result["is_stream"]:
        return StreamingResponse(
            iter([result["body"]]),
            status_code=result["status_code"],
            headers={
                "content-type": "text/event-stream",
                "x-sentinel-cost": str(result["cost_usd"]),
                "x-sentinel-request-id": result["request_id"],
                "cache-control": "no-cache",
            },
        )
    return Response(
        content=result["body"],
        status_code=result["status_code"],
        headers={
            "content-type": "application/json",
            "x-sentinel-cost": str(result["cost_usd"]),
            "x-sentinel-request-id": result["request_id"],
        },
    )


@app.get("/sentinel/health")
async def health():
    return {"status": "ok", "version": "0.3.0", "budget_mode": BUDGET_MODE}


@app.get("/sentinel/stats")
async def stats(project: str = "default", days: int = 30, _: bool = Depends(verify_admin)):
    data = await get_stats(project, days)
    budget = await get_budget(project)
    return {**data, "budget": budget}


@app.get("/sentinel/calls")
async def calls(limit: int = 50, project: str = None, _: bool = Depends(verify_admin)):
    data = await get_recent_calls(limit, project)
    return {"calls": data}


@app.post("/sentinel/budget")
async def set_budget(project: str = "default", daily: float = 5.0, monthly: float = 50.0, _: bool = Depends(verify_admin)):
    await setup_budget(project, daily, monthly)
    return {"status": "ok", "project": project, "daily": daily, "monthly": monthly}


@app.get("/sentinel/budget")
async def budget_status(project: str = "default", _: bool = Depends(verify_admin)):
    budget = await get_budget(project)
    daily = await get_daily_cost(project)
    monthly = await get_monthly_cost(project)
    return {
        **budget,
        "daily_cost": daily,
        "monthly_cost": monthly,
        "daily_pct": round(daily / budget["daily_limit"] * 100, 1) if budget["daily_limit"] > 0 else 0,
        "monthly_pct": round(monthly / budget["monthly_limit"] * 100, 1) if budget["monthly_limit"] > 0 else 0,
    }


@app.get("/sentinel/export/csv")
async def export(project: str = "default", days: int = 30, _: bool = Depends(verify_admin)):
    csv_data = await export_csv(project, days)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"content-disposition": f"attachment; filename=sentinel_{project}_{days}d.csv"},
    )


@app.get("/sentinel/compare")
async def compare(project: str = "default", days: int = 30, _: bool = Depends(verify_admin)):
    data = await get_stats(project, days)
    return {"models": data["by_model"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
