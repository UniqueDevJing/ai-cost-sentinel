"""
预算告警 — 检测费用是否超出预算，支持 Webhook 通知
"""

from __future__ import annotations

import os
import httpx

from tracker.db import get_daily_cost, get_monthly_cost, get_budget

WEBHOOK_URL = os.getenv("SENTINEL_WEBHOOK_URL", "")


class BudgetAlert:
    """预算告警结果"""

    def __init__(self, project: str):
        self.project = project
        self.daily_exceeded = False
        self.monthly_exceeded = False
        self.daily_usage_pct = 0.0
        self.monthly_usage_pct = 0.0
        self.daily_cost = 0.0
        self.monthly_cost = 0.0
        self.daily_limit = 0.0
        self.monthly_limit = 0.0
        self.messages: list[str] = []
        self.webhook_sent = False

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "daily_exceeded": self.daily_exceeded,
            "monthly_exceeded": self.monthly_exceeded,
            "daily_usage_pct": round(self.daily_usage_pct, 1),
            "monthly_usage_pct": round(self.monthly_usage_pct, 1),
            "daily_cost": self.daily_cost,
            "monthly_cost": self.monthly_cost,
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "alerts": self.messages,
            "webhook_sent": self.webhook_sent,
        }


async def check_budget(project: str = "default") -> BudgetAlert:
    """检查预算状态，超支时发送 Webhook 通知"""
    alert = BudgetAlert(project)

    budget = await get_budget(project)
    alert.daily_limit = budget["daily_limit"]
    alert.monthly_limit = budget["monthly_limit"]

    daily = await get_daily_cost(project)
    monthly = await get_monthly_cost(project)

    alert.daily_cost = daily["cost_usd"]
    alert.monthly_cost = monthly["cost_usd"]

    if alert.daily_limit > 0:
        alert.daily_usage_pct = (alert.daily_cost / alert.daily_limit) * 100
        if alert.daily_usage_pct >= 100:
            alert.daily_exceeded = True
            alert.messages.append(
                f"日预算已超支！{alert.daily_cost:.4f} / {alert.daily_limit:.2f} USD"
            )
        elif alert.daily_usage_pct >= 80:
            alert.messages.append(
                f"日预算使用 {alert.daily_usage_pct:.0f}%，已用 {alert.daily_cost:.4f} / {alert.daily_limit:.2f} USD"
            )

    if alert.monthly_limit > 0:
        alert.monthly_usage_pct = (alert.monthly_cost / alert.monthly_limit) * 100
        if alert.monthly_usage_pct >= 100:
            alert.monthly_exceeded = True
            alert.messages.append(
                f"月预算已超支！{alert.monthly_cost:.4f} / {alert.monthly_limit:.2f} USD"
            )
        elif alert.monthly_usage_pct >= 80:
            alert.messages.append(
                f"月预算使用 {alert.monthly_usage_pct:.0f}%，已用 {alert.monthly_cost:.4f} / {alert.monthly_limit:.2f} USD"
            )

    # 发送 Webhook
    if alert.messages and WEBHOOK_URL:
        await _send_webhook(alert)

    return alert


async def _send_webhook(alert: BudgetAlert):
    """发送 Slack 兼容 Webhook 通知"""
    text = "\n".join(f"[{'超支' if '超支' in a else '警告'}] {a}" for a in alert.messages)
    payload = {
        "text": f"*AI Cost Sentinel — {alert.project}*\n{text}",
        "attachments": [{
            "fields": [
                {"title": "日用量", "value": f"${alert.daily_cost:.2f} / ${alert.daily_limit:.2f}", "short": True},
                {"title": "月用量", "value": f"${alert.monthly_cost:.2f} / ${alert.monthly_limit:.2f}", "short": True},
            ]
        }]
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(WEBHOOK_URL, json=payload, timeout=10)
            alert.webhook_sent = True
    except Exception:
        pass
