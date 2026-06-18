"""
SQLite 数据库操作 — 记录每次 API 调用和 Token 消耗
"""

from __future__ import annotations

import aiosqlite
import json
import time
from datetime import datetime, date

from config import DB_PATH


async def init_db() -> None:
    """初始化数据库表"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                model TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                project TEXT DEFAULT 'default',
                user_id TEXT DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                latency_ms INTEGER DEFAULT 0,
                status_code INTEGER DEFAULT 200,
                error_msg TEXT DEFAULT '',
                request_id TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_date ON api_calls(date)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_project ON api_calls(project)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL UNIQUE,
                daily_limit REAL NOT NULL DEFAULT 5.0,
                monthly_limit REAL NOT NULL DEFAULT 50.0,
                alert_enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.commit()


async def log_call(
    model: str,
    endpoint: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    status_code: int = 200,
    project: str = "default",
    user_id: str = "",
    error_msg: str = "",
    request_id: str = "",
) -> None:
    """记录一次 API 调用"""
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO api_calls
               (timestamp, date, model, endpoint, project, user_id,
                input_tokens, output_tokens, cost_usd, latency_ms,
                status_code, error_msg, request_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now.isoformat(),
                now.strftime("%Y-%m-%d"),
                model,
                endpoint,
                project,
                user_id,
                input_tokens,
                output_tokens,
                cost_usd,
                latency_ms,
                status_code,
                error_msg,
                request_id,
            ),
        )
        await db.commit()


async def get_daily_cost(project: str = "default", target_date: str = None) -> dict:
    """查询某天的费用统计"""
    d = target_date or date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall(
            """SELECT COALESCE(SUM(cost_usd), 0), COALESCE(SUM(input_tokens), 0),
                      COALESCE(SUM(output_tokens), 0), COUNT(*)
               FROM api_calls WHERE project = ? AND date = ?""",
            (project, d),
        )
        cost, it, ot, count = row[0]
        return {"date": d, "cost_usd": round(cost, 6), "input_tokens": it,
                "output_tokens": ot, "calls": count}


async def get_monthly_cost(project: str = "default", year_month: str = None) -> dict:
    """查询某月的费用统计"""
    ym = year_month or datetime.now().strftime("%Y-%m")
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall(
            """SELECT COALESCE(SUM(cost_usd), 0), COALESCE(SUM(input_tokens), 0),
                      COALESCE(SUM(output_tokens), 0), COUNT(*)
               FROM api_calls WHERE project = ? AND date LIKE ?""",
            (project, f"{ym}%"),
        )
        cost, it, ot, count = row[0]
        return {"month": ym, "cost_usd": round(cost, 6), "input_tokens": it,
                "output_tokens": ot, "calls": count}


async def get_recent_calls(limit: int = 50) -> list[dict]:
    """查询最近的 API 调用"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT * FROM api_calls ORDER BY id DESC LIMIT ?""", (limit,)
        )
        return [dict(r) for r in rows]


async def get_stats(project: str = "default", days: int = 30) -> dict:
    """获取综合统计"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 按模型汇总
        rows = await db.execute_fetchall(
            """SELECT model, COUNT(*) as calls, COALESCE(SUM(cost_usd), 0) as cost,
                      COALESCE(SUM(input_tokens), 0) as input_tokens,
                      COALESCE(SUM(output_tokens), 0) as output_tokens
               FROM api_calls WHERE project = ?
               AND date >= date('now', ?)
               GROUP BY model ORDER BY cost DESC""",
            (project, f"-{days} days"),
        )
        by_model = [{"model": r[0], "calls": r[1], "cost_usd": round(r[2], 6),
                     "input_tokens": r[3], "output_tokens": r[4]} for r in rows]

        # 按日汇总
        rows2 = await db.execute_fetchall(
            """SELECT date, COALESCE(SUM(cost_usd), 0), COUNT(*)
               FROM api_calls WHERE project = ?
               AND date >= date('now', ?)
               GROUP BY date ORDER BY date ASC""",
            (project, f"-{days} days"),
        )
        by_day = [{"date": r[0], "cost_usd": round(r[1], 6), "calls": r[2]} for r in rows2]

        return {"by_model": by_model, "by_day": by_day}


async def setup_budget(project: str, daily: float, monthly: float) -> None:
    """设置项目预算"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO budgets (project, daily_limit, monthly_limit)
               VALUES (?, ?, ?)""",
            (project, daily, monthly),
        )
        await db.commit()


async def get_budget(project: str) -> dict:
    """获取项目预算配置"""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall(
            "SELECT daily_limit, monthly_limit FROM budgets WHERE project = ?",
            (project,),
        )
        if row:
            return {"daily_limit": row[0][0], "monthly_limit": row[0][1]}
        return {"daily_limit": 5.0, "monthly_limit": 50.0}


async def export_csv(project: str = "default", days: int = 30) -> str:
    """导出调用记录为 CSV 字符串"""
    import csv, io
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            """SELECT timestamp, model, endpoint, project, input_tokens, output_tokens,
                      cost_usd, latency_ms, status_code
               FROM api_calls WHERE project = ?
               AND date >= date('now', ?)
               ORDER BY id DESC""",
            (project, f"-{days} days"),
        )
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["timestamp", "model", "endpoint", "project", "input_tokens",
                "output_tokens", "cost_usd", "latency_ms", "status_code"])
    for r in rows:
        w.writerow(r)
    return output.getvalue()


async def compare_models(project: str = "default", days: int = 30) -> list[dict]:
    """对比各模型的成本效率"""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            """SELECT model,
                      COUNT(*) as calls,
                      COALESCE(SUM(cost_usd), 0) as total_cost,
                      COALESCE(SUM(input_tokens), 0) as total_input,
                      COALESCE(SUM(output_tokens), 0) as total_output,
                      COALESCE(AVG(cost_usd), 0) as avg_cost,
                      COALESCE(AVG(latency_ms), 0) as avg_latency
               FROM api_calls WHERE project = ?
               AND date >= date('now', ?)
               GROUP BY model ORDER BY total_cost DESC""",
            (project, f"-{days} days"),
        )
    result = []
    for r in rows:
        total_tokens = r[3] + r[4]
        cost_per_1k = round(r[2] / total_tokens * 1000, 6) if total_tokens > 0 else 0
        result.append({
            "model": r[0],
            "calls": r[1],
            "total_cost_usd": round(r[2], 6),
            "total_input_tokens": r[3],
            "total_output_tokens": r[4],
            "avg_cost_per_call_usd": round(r[5], 6),
            "avg_latency_ms": round(r[6], 1),
            "cost_per_1k_tokens_usd": cost_per_1k,
        })
    return result
