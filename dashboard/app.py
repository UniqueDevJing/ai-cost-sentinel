"""AI Cost Sentinel — Streamlit 仪表盘"""

import os
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import date, timedelta

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent.parent / "sentinel-proxy" / "sentinel.db"))
PRICING = {
    "gpt-4o": (2.50, 10.00), "gpt-4o-mini": (0.15, 0.60), "gpt-4-turbo": (10.00, 30.00),
    "claude-sonnet-4-6": (3.00, 15.00), "claude-opus-4-7": (15.00, 75.00), "claude-haiku-4-5": (0.80, 4.00),
    "deepseek-chat": (0.27, 1.10), "deepseek-reasoner": (0.55, 2.19),
    "qwen-plus": (0.80, 2.80), "qwen-turbo": (0.30, 0.60), "qwen-max": (2.40, 9.60),
}

st.set_page_config(page_title="AI Cost Sentinel", page_icon="📊", layout="wide")
st.title("AI Cost Sentinel — 成本追踪仪表盘")

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row


def run_query(query: str, params=()):
    return [dict(r) for r in conn.execute(query, params).fetchall()]


# Sidebar — project & date filter
st.sidebar.header("筛选")
project = st.sidebar.text_input("项目名称", "default")
days = st.sidebar.slider("统计天数", 1, 90, 30)

# Top metrics
rows = run_query(
    "SELECT COUNT(*) as calls, COALESCE(SUM(cost_usd),0) as cost, "
    "COUNT(DISTINCT model) as models "
    "FROM calls WHERE project=? AND created_at >= datetime('now','-'||?||' days')",
    (project, days),
)
r = rows[0]
col1, col2, col3, col4 = st.columns(4)
col1.metric("总调用次数", r["calls"])
col2.metric("总费用", f"${r['cost']:.4f}")
col3.metric("使用模型数", r["models"])

# Budget check
budget_row = run_query("SELECT * FROM budgets WHERE project=?", (project,))
daily_limit = budget_row[0]["daily_limit"] if budget_row else 5.0
monthly_limit = budget_row[0]["monthly_limit"] if budget_row else 50.0

daily_cost = run_query(
    "SELECT COALESCE(SUM(cost_usd),0) as t FROM calls WHERE project=? AND DATE(created_at)=DATE('now')",
    (project,),
)[0]["t"]
monthly_cost = run_query(
    "SELECT COALESCE(SUM(cost_usd),0) as t FROM calls WHERE project=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",
    (project,),
)[0]["t"]

daily_pct = daily_cost / daily_limit * 100 if daily_limit > 0 else 0
monthly_pct = monthly_cost / monthly_limit * 100 if monthly_limit > 0 else 0
status = "🟢 正常"
if daily_pct >= 100 or monthly_pct >= 100:
    status = "🔴 超支"
elif daily_pct >= 80 or monthly_pct >= 80:
    status = "🟡 警告"
col4.metric("预算状态", status)

# Budget gauges
st.subheader("预算使用情况")
cg1, cg2 = st.columns(2)
with cg1:
    st.caption(f"今日: ${daily_cost:.3f} / ${daily_limit:.2f}")
    st.progress(min(daily_pct / 100, 1.0))
with cg2:
    st.caption(f"本月: ${monthly_cost:.3f} / ${monthly_limit:.2f}")
    st.progress(min(monthly_pct / 100, 1.0))

# Charts
st.subheader("费用趋势")
chart_data = run_query(
    "SELECT DATE(created_at) as day, SUM(cost_usd) as cost, COUNT(*) as calls "
    "FROM calls WHERE project=? AND created_at >= datetime('now','-'||?||' days') "
    "GROUP BY DATE(created_at) ORDER BY day",
    (project, days),
)
if chart_data:
    df_chart = pd.DataFrame(chart_data)
    c1, c2 = st.columns(2)
    with c1:
        st.line_chart(df_chart.set_index("day")["cost"], use_container_width=True)
    with c2:
        st.bar_chart(df_chart.set_index("day")["calls"], use_container_width=True)

# Model breakdown
st.subheader("模型成本占比")
model_data = run_query(
    "SELECT model, SUM(cost_usd) as cost, COUNT(*) as calls "
    "FROM calls WHERE project=? AND created_at >= datetime('now','-'||?||' days') "
    "GROUP BY model ORDER BY cost DESC",
    (project, days),
)
if model_data:
    df_model = pd.DataFrame(model_data)
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(df_model, use_container_width=True, hide_index=True)
    with c2:
        if len(df_model) > 0 and df_model["cost"].sum() > 0:
            st.bar_chart(df_model.set_index("model")["cost"], use_container_width=True)

# Recent calls
st.subheader("最近调用记录")
calls = run_query(
    "SELECT created_at, model, endpoint, input_tokens, output_tokens, cost_usd, latency_ms, status_code "
    "FROM calls WHERE project=? ORDER BY id DESC LIMIT 50",
    (project,),
)
if calls:
    df_calls = pd.DataFrame(calls)
    st.dataframe(df_calls, use_container_width=True, hide_index=True)

# Export
st.subheader("导出")
if st.button("导出 CSV"):
    import csv, io
    export_rows = run_query(
        "SELECT * FROM calls WHERE project=? AND created_at >= datetime('now','-'||?||' days') ORDER BY id DESC",
        (project, days),
    )
    if export_rows:
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=export_rows[0].keys())
        w.writeheader()
        w.writerows(export_rows)
        st.download_button("下载 CSV", out.getvalue(), f"sentinel_{project}_{days}d.csv", "text/csv")

conn.close()
