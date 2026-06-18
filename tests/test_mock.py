"""
Mock tests for AI Cost Sentinel — no real API key required.
Tests config, tracker, alerter, and proxy modules offline.
"""

from __future__ import annotations

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sentinel-proxy"))


# ============================================================
# Config Tests
# ============================================================

class TestConfig:
    """Configuration and pricing tests"""

    def test_all_models_have_pricing(self):
        from config import MODEL_PRICING
        for model, price in MODEL_PRICING.items():
            assert "input" in price, f"{model} missing input"
            assert "output" in price, f"{model} missing output"
            assert price["input"] > 0, f"{model} input price should be > 0"
            assert price["output"] > 0, f"{model} output price should be > 0"

    def test_default_fallback(self):
        from config import get_model_price, MODEL_PRICING
        price = get_model_price("nonexistent-model-v42")
        assert price == MODEL_PRICING["default"]

    def test_fuzzy_match(self):
        from config import get_model_price, MODEL_PRICING
        price = get_model_price("gpt-4o-2024-08-06")
        assert price == MODEL_PRICING["gpt-4o"]

    def test_calculate_cost_gpt4o(self):
        from config import calculate_cost
        cost = calculate_cost("gpt-4o", 1000, 500)
        assert cost == 0.0075

    def test_calculate_cost_qwen_plus(self):
        from config import calculate_cost
        cost = calculate_cost("qwen-plus", 1000000, 1000000)
        assert cost == pytest.approx(3.60, rel=0.01)

    def test_qwen_turbo_pricing(self):
        from config import get_model_price
        price = get_model_price("qwen-turbo")
        assert price["input"] == 0.30
        assert price["output"] == 0.60

    def test_claude_sonnet_pricing(self):
        from config import get_model_price
        price = get_model_price("claude-sonnet-4-6")
        assert price["input"] == 3.00
        assert price["output"] == 15.00

    def test_claude_haiku_pricing(self):
        from config import get_model_price
        price = get_model_price("claude-haiku-4-5")
        assert price["input"] == 0.80
        assert price["output"] == 4.00

    def test_claude_opus_pricing(self):
        from config import get_model_price
        price = get_model_price("claude-opus-4-7")
        assert price["input"] == 15.00
        assert price["output"] == 75.00


# ============================================================
# Tracker Tests (SQLite)
# ============================================================

@pytest.fixture
def temp_db():
    """Temporary SQLite database for testing"""
    import config
    import tracker.db as dbmod

    tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = os.path.join(tempdir.name, "test.db")

    original_db = config.DB_PATH
    config.DB_PATH = db_path
    dbmod.DB_PATH = db_path  # must update both: config + tracker.db imports
    dbmod._pool = None

    yield db_path

    config.DB_PATH = original_db
    dbmod.DB_PATH = original_db
    dbmod._pool = None


class TestTracker:

    async def _init(self):
        from tracker.db import init_db
        await init_db()

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, temp_db):
        from tracker.db import init_db
        await init_db()
        import aiosqlite
        async with aiosqlite.connect(temp_db) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            assert "api_calls" in tables
            assert "budgets" in tables

    @pytest.mark.asyncio
    async def test_log_and_retrieve(self, temp_db):
        from tracker.db import init_db, log_call, get_recent_calls
        await init_db()

        await log_call(
            model="gpt-4o",
            endpoint="/v1/chat/completions",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0075,
            latency_ms=1250,
            status_code=200,
            project="test-project",
        )

        calls = await get_recent_calls(limit=10)
        assert len(calls) >= 1
        call = [c for c in calls if c["project"] == "test-project"][0]
        assert call["model"] == "gpt-4o"
        assert call["cost_usd"] == 0.0075

    @pytest.mark.asyncio
    async def test_daily_cost(self, temp_db):
        from tracker.db import init_db, log_call, get_daily_cost
        from datetime import date
        await init_db()

        await log_call("gpt-4o", "/v1", 100, 50, 0.001, 100, project="dd")
        await log_call("gpt-4o", "/v1", 200, 100, 0.002, 100, project="dd")

        result = await get_daily_cost("dd", date.today().isoformat())
        assert result["calls"] == 2

    @pytest.mark.asyncio
    async def test_setup_and_get_budget(self, temp_db):
        from tracker.db import init_db, setup_budget, get_budget
        await init_db()

        await setup_budget("bt", daily=20.0, monthly=200.0)
        budget = await get_budget("bt")
        assert budget["daily_limit"] == 20.0
        assert budget["monthly_limit"] == 200.0

    @pytest.mark.asyncio
    async def test_default_budget(self, temp_db):
        from tracker.db import init_db, get_budget
        await init_db()

        budget = await get_budget("no-such-project")
        assert budget["daily_limit"] == 5.0
        assert budget["monthly_limit"] == 50.0

    @pytest.mark.asyncio
    async def test_export_csv(self, temp_db):
        from tracker.db import init_db, log_call, export_csv
        await init_db()

        await log_call("gpt-4o", "/v1", 100, 50, 0.001, 100, project="csvtest")
        csv = await export_csv("csvtest", days=1)
        lines = csv.strip().split("\n")
        assert lines[0].startswith("timestamp")
        assert len(lines) >= 2

    @pytest.mark.asyncio
    async def test_compare_models(self, temp_db):
        from tracker.db import init_db, log_call, compare_models
        await init_db()

        await log_call("gpt-4o", "/v1", 1000, 500, 0.0075, 200, project="cmp")
        await log_call("gpt-4o-mini", "/v1", 500, 250, 0.00015, 100, project="cmp")

        result = await compare_models("cmp", days=1)
        assert len(result) >= 1


# ============================================================
# Alerter Tests
# ============================================================

class TestAlerter:

    def test_budget_alert_class(self):
        from alerter.budget import BudgetAlert

        alert = BudgetAlert("test-proj")
        alert.daily_cost = 6.0
        alert.daily_limit = 5.0
        alert.daily_usage_pct = 120.0
        alert.daily_exceeded = True
        alert.messages.append("日预算已超支！6.00 / 5.00 USD")

        d = alert.to_dict()
        assert d["project"] == "test-proj"
        assert d["daily_exceeded"] is True
        assert len(d["alerts"]) == 1

    def test_budget_alert_not_exceeded(self):
        from alerter.budget import BudgetAlert

        alert = BudgetAlert("normal")
        alert.daily_cost = 2.0
        alert.daily_limit = 5.0
        alert.daily_usage_pct = 40.0

        d = alert.to_dict()
        assert d["daily_exceeded"] is False
        assert d["monthly_exceeded"] is False

    def test_to_dict_has_all_keys(self):
        from alerter.budget import BudgetAlert

        alert = BudgetAlert("full")
        d = alert.to_dict()
        for key in ["project", "daily_exceeded", "monthly_exceeded",
                     "daily_usage_pct", "monthly_usage_pct",
                     "daily_cost", "monthly_cost", "daily_limit",
                     "monthly_limit", "alerts", "webhook_sent"]:
            assert key in d, f"Missing key: {key}"


# ============================================================
# Forwarder Tests
# ============================================================

class TestForwarder:

    def test_extract_model_from_body(self):
        from proxy.forwarder import _extract_model
        body = b'{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'
        assert _extract_model(body) == "gpt-4o"

    def test_extract_model_missing(self):
        from proxy.forwarder import _extract_model
        assert _extract_model(b'{"messages":[]}') == ""

    def test_extract_model_invalid_json(self):
        from proxy.forwarder import _extract_model
        assert _extract_model(b'not json') == ""

    def test_is_stream_request_true(self):
        from proxy.forwarder import _is_stream_request
        body = b'{"model":"gpt-4o","stream":true}'
        assert _is_stream_request(body) is True

    def test_is_stream_request_false(self):
        from proxy.forwarder import _is_stream_request
        body = b'{"model":"gpt-4o"}'
        assert _is_stream_request(body) is False

    def test_is_stream_request_invalid(self):
        from proxy.forwarder import _is_stream_request
        assert _is_stream_request(b'bad data') is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
