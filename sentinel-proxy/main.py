"""
AI Cost Sentinel — 主入口

启动方式:
    python main.py
    SENTINEL_PORT=8888 python main.py

使用方式 (客户端):
    将 API base_url 从 https://api.openai.com/v1
    改为 http://localhost:8000/v1
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse

from config import PROXY_HOST, PROXY_PORT
from tracker.db import init_db, get_daily_cost, get_monthly_cost, get_stats, get_recent_calls, setup_budget, export_csv, compare_models
from proxy.forwarder import forward_request
from alerter.budget import check_budget


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"\n  Cost Sentinel 已启动: http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"  上游 API: (从请求头透传)\n")
    yield


app = FastAPI(
    title="AI Cost Sentinel",
    version="0.2.0",
    description="轻量 AI API 成本追踪代理 — 一行代码不改，透明拦截统计",
    lifespan=lifespan,
)


# ============================================================
# 透明代理 — 拦截所有 /v1/* 请求
# ============================================================

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_v1(request: Request, path: str):
    """透明代理：转发所有 OpenAI 兼容 API 请求"""
    body = await request.body()
    project = request.headers.get("x-sentinel-project", "default")

    result = await forward_request(
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        body=body,
        query_params=str(request.query_params) if request.query_params else "",
        project=project,
    )

    # 流式响应
    if result["is_stream"]:
        return StreamingResponse(
            iter([result["body"]]),
            status_code=result["status_code"],
            headers={
                "content-type": "text/event-stream",
                "x-sentinel-cost": str(result["cost_usd"]),
                "x-sentinel-request-id": result["request_id"],
            },
        )

    # 普通 JSON 响应
    return Response(
        content=result["body"],
        status_code=result["status_code"],
        headers={
            "content-type": "application/json",
            "x-sentinel-cost": str(result["cost_usd"]),
            "x-sentinel-request-id": result["request_id"],
        },
    )


# ============================================================
# Sentinel 管理 API
# ============================================================

@app.get("/sentinel/health")
async def health():
    return {"status": "ok", "service": "AI Cost Sentinel", "version": "0.2.0"}


@app.get("/sentinel/stats")
async def stats(project: str = "default", days: int = 30):
    """获取综合统计"""
    data = await get_stats(project, days)
    budget = await check_budget(project)
    return {**data, "budget": budget.to_dict()}


@app.get("/sentinel/calls")
async def recent_calls(limit: int = 50):
    """获取最近的 API 调用记录"""
    return {"calls": await get_recent_calls(limit)}


@app.post("/sentinel/budget")
async def set_budget(project: str = "default", daily: float = 5.0, monthly: float = 50.0):
    """设置项目预算"""
    await setup_budget(project, daily, monthly)
    return {"ok": True, "project": project, "daily_limit": daily, "monthly_limit": monthly}


@app.get("/sentinel/budget")
async def get_budget_status(project: str = "default"):
    """查看预算状态"""
    alert = await check_budget(project)
    return alert.to_dict()


@app.get("/sentinel/export/csv")
async def export_calls_csv(project: str = "default", days: int = 30):
    """导出调用记录为 CSV"""
    from fastapi.responses import PlainTextResponse
    csv_data = await export_csv(project, days)
    return PlainTextResponse(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sentinel-{project}-{days}d.csv"}
    )


@app.get("/sentinel/compare")
async def compare_model_costs(project: str = "default", days: int = 30):
    """对比各模型的成本效率"""
    models = await compare_models(project, days)
    return {"project": project, "days": days, "models": models}


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=PROXY_HOST, port=PROXY_PORT, reload=False)
