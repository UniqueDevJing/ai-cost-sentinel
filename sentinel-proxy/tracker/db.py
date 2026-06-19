"""SQLite 异步操作"""

from __future__ import annotations
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sentinel.db"
_pool = None


async def get_db():
    global _pool
    if _pool is None:
        _pool = await aiosqlite.connect(DB_PATH)
        _pool.row_factory = aiosqlite.Row
        await _pool.execute("PRAGMA journal_mode=WAL")
    return _pool


async def init_db():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL DEFAULT '',
            project TEXT NOT NULL DEFAULT 'default',
            model TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status_code INTEGER NOT NULL DEFAULT 0,
            error_msg TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            project TEXT PRIMARY KEY,
            daily_limit REAL NOT NULL DEFAULT 5.0,
            monthly_limit REAL NOT NULL DEFAULT 50.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_calls_project ON calls(project)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_calls_created ON calls(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_calls_model ON calls(model)")
    await db.commit()


async def log_call(**kw):
    db = await get_db()
    await db.execute(
        """INSERT INTO calls
           (request_id, project, model, endpoint, input_tokens, output_tokens,
            cost_usd, latency_ms, status_code, error_msg)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            kw.get("request_id", ""),
            kw.get("project", "default"),
            kw.get("model", "unknown"),
            kw.get("endpoint", ""),
            kw.get("input_tokens", 0),
            kw.get("output_tokens", 0),
            kw.get("cost_usd", 0.0),
            kw.get("latency_ms", 0),
            kw.get("status_code", 0),
            kw.get("error_msg", ""),
        ),
    )
    await db.commit()


async def get_stats(project: str, days: int = 30):
    db = await get_db()
    cur = await db.execute(
        """SELECT model, COUNT(*) as call_count, SUM(input_tokens) as total_input,
                  SUM(output_tokens) as total_output, SUM(cost_usd) as total_cost,
                  AVG(latency_ms) as avg_latency
           FROM calls
           WHERE project=? AND created_at >= datetime('now','-'||?||' days')
           GROUP BY model ORDER BY total_cost DESC""",
        (project, days),
    )
    by_model = [dict(r) for r in await cur.fetchall()]
    cur = await db.execute(
        """SELECT DATE(created_at) as day, SUM(cost_usd) as daily_cost,
                  COUNT(*) as call_count
           FROM calls
           WHERE project=? AND created_at >= datetime('now','-'||?||' days')
           GROUP BY DATE(created_at) ORDER BY day""",
        (project, days),
    )
    by_day = [dict(r) for r in await cur.fetchall()]
    return {
        "by_model": by_model,
        "by_day": by_day,
        "total_calls": sum(r["call_count"] for r in by_model),
        "total_cost": sum(r["total_cost"] for r in by_model),
    }


async def get_recent_calls(limit: int = 50, project: str = None):
    db = await get_db()
    q = """SELECT id, request_id, project, model, endpoint, input_tokens,
                  output_tokens, cost_usd, latency_ms, status_code, error_msg, created_at
           FROM calls"""
    params = []
    if project:
        q += " WHERE project=?"
        params.append(project)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cur = await db.execute(q, params)
    return [dict(r) for r in await cur.fetchall()]


async def setup_budget(project: str, daily: float, monthly: float):
    db = await get_db()
    await db.execute(
        """INSERT INTO budgets (project, daily_limit, monthly_limit, updated_at)
           VALUES (?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(project) DO UPDATE SET
             daily_limit=excluded.daily_limit,
             monthly_limit=excluded.monthly_limit,
             updated_at=CURRENT_TIMESTAMP""",
        (project, daily, monthly),
    )
    await db.commit()


async def get_budget(project: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM budgets WHERE project=?", (project,))
    row = await cur.fetchone()
    if row is None:
        return {"project": project, "daily_limit": 5.0, "monthly_limit": 50.0}
    return dict(row)


async def get_daily_cost(project: str) -> float:
    db = await get_db()
    cur = await db.execute(
        "SELECT COALESCE(SUM(cost_usd),0) as t FROM calls WHERE project=? AND DATE(created_at)=DATE('now')",
        (project,),
    )
    return (await cur.fetchone())["t"]


async def get_monthly_cost(project: str) -> float:
    db = await get_db()
    cur = await db.execute(
        "SELECT COALESCE(SUM(cost_usd),0) as t FROM calls WHERE project=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",
        (project,),
    )
    return (await cur.fetchone())["t"]


async def export_csv(project: str, days: int = 30) -> str:
    import csv
    import io

    db = await get_db()
    cur = await db.execute(
        """SELECT id, request_id, project, model, endpoint, input_tokens,
                  output_tokens, cost_usd, latency_ms, status_code, error_msg, created_at
           FROM calls
           WHERE project=? AND created_at >= datetime('now','-'||?||' days')
           ORDER BY id DESC""",
        (project, days),
    )
    rows = await cur.fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "ID", "Request ID", "Project", "Model", "Endpoint",
        "Input Tokens", "Output Tokens", "Cost (USD)", "Latency (ms)",
        "Status Code", "Error", "Created At",
    ])
    for r in rows:
        w.writerow([r[i] for i in range(len(r))])
    return out.getvalue()
