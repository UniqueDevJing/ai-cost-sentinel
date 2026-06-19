"""预算告警"""

from __future__ import annotations
import httpx
from config import WEBHOOK_URL
from tracker.db import get_daily_cost, get_monthly_cost, get_budget


async def check_and_alert(project: str = "default"):
    budget = await get_budget(project)
    daily = await get_daily_cost(project)
    monthly = await get_monthly_cost(project)
    warnings = []

    if budget["daily_limit"] > 0:
        pct = daily / budget["daily_limit"] * 100
        if pct >= 100:
            warnings.append(f"[{project}] 日预算超支: ${daily:.2f}/${budget['daily_limit']:.2f}")
        elif pct >= 80:
            warnings.append(f"[{project}] 日预算使用 {pct:.0f}%")

    if budget["monthly_limit"] > 0:
        pct = monthly / budget["monthly_limit"] * 100
        if pct >= 100:
            warnings.append(f"[{project}] 月预算超支: ${monthly:.2f}/${budget['monthly_limit']:.2f}")
        elif pct >= 80:
            warnings.append(f"[{project}] 月预算使用 {pct:.0f}%")

    if warnings and WEBHOOK_URL:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(WEBHOOK_URL, json={"text": "\n".join(warnings)}, timeout=10)
        except Exception:
            pass

    return warnings
