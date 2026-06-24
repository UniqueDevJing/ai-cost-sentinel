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
        from config import PRICING
        for model, price in PRICING.items():
            assert isinstance(price, tuple), f"{model} should be tuple"
            assert len(price) == 2, f"{model} should have (input, output)"
            assert price[0] > 0, f"{model} input price should be > 0"
            assert price[1] > 0, f"{model} output price should be > 0"

    def test_default_fallback(self):
        from config import PRICING, calculate_cost
        cost = calculate_cost("nonexistent-model-v42", 1000, 500)
        assert cost == 1000 * 1.00 / 1e6 + 500 * 3.00 / 1e6

    def test_calculate_cost_gpt4o(self):
        from config import calculate_cost
        cost = calculate_cost("gpt-4o", 1000, 500)
        assert cost == 1000 * 2.50 / 1e6 + 500 * 10.00 / 1e6

    def test_calculate_cost_qwen_plus(self):
        from config import calculate_cost
        cost = calculate_cost("qwen-plus", 1000000, 1000000)
        assert cost == pytest.approx(3.60, rel=0.01)

    def test_qwen_turbo_pricing(self):
        from config import PRICING
        price = PRICING["qwen-turbo"]
        assert price[0] == 0.30
        assert price[1] == 0.60

    def test_claude_sonnet_pricing(self):
        from config import PRICING
        price = PRICING["claude-sonnet-4-6"]
        assert price[0] == 3.00
        assert price[1] == 15.00

    def test_claude_haiku_pricing(self):
        from config import PRICING
        price = PRICING["claude-haiku-4-5"]
        assert price[0] == 0.80
        assert price[1] == 4.00

    def test_claude_opus_pricing(self):
        from config import PRICING
        price = PRICING["claude-opus-4-7"]
        assert price[0] == 15.00
        assert price[1] == 75.00


# ============================================================
# Tracker Tests (SQLite)
# ============================================================

@pytest.fixture
def temp_db():
    """Temporary SQLite database for testing"""
    import tracker.db as dbmod

    tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = os.path.join(tempdir.name, "test.db")

    original_db = str(dbmod.DB_PATH)
    dbmod.DB_PATH = db_path
    dbmod._pool = None

    yield db_path

    dbmod.DB_PATH = original_db
    dbmod._pool = None


class TestTracker:

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
            assert "calls" in tables
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
            request_id="test-1",
            error_msg="",
        )

        calls = await get_recent_calls(limit=10)
        assert len(calls) >= 1
        call = [c for c in calls if c["project"] == "test-project"][0]
        assert call["model"] == "gpt-4o"
        assert call["cost_usd"] == 0.0075

    @pytest.mark.asyncio
    async def test_daily_cost(self, temp_db):
        from tracker.db import init_db, log_call, get_daily_cost
        await init_db()

        await log_call(model="gpt-4o", endpoint="/v1", input_tokens=100, output_tokens=50,
                       cost_usd=0.001, latency_ms=100, project="dd",
                       request_id="r1", error_msg="", status_code=200)
        await log_call(model="gpt-4o", endpoint="/v1", input_tokens=200, output_tokens=100,
                       cost_usd=0.002, latency_ms=100, project="dd",
                       request_id="r2", error_msg="", status_code=200)

        daily = await get_daily_cost("dd")
        assert daily > 0

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

        await log_call(model="gpt-4o", endpoint="/v1", input_tokens=100, output_tokens=50,
                       cost_usd=0.001, latency_ms=100, project="csvtest",
                       request_id="r1", error_msg="", status_code=200)
        csv = await export_csv("csvtest", days=1)
        lines = csv.strip().split("\n")
        assert lines[0].startswith("ID")
        assert len(lines) >= 2

    @pytest.mark.asyncio
    async def test_compare_stats(self, temp_db):
        from tracker.db import init_db, log_call, get_stats
        await init_db()

        await log_call(model="gpt-4o", endpoint="/v1", input_tokens=1000, output_tokens=500,
                       cost_usd=0.0075, latency_ms=200, project="cmp",
                       request_id="r1", error_msg="", status_code=200)
        await log_call(model="gpt-4o-mini", endpoint="/v1", input_tokens=500, output_tokens=250,
                       cost_usd=0.00015, latency_ms=100, project="cmp",
                       request_id="r2", error_msg="", status_code=200)

        result = await get_stats("cmp", days=1)
        assert "by_model" in result


# ============================================================
# Alerter Tests
# ============================================================

class TestAlerter:

    @pytest.mark.asyncio
    async def test_check_and_alert_no_webhook(self):
        from alerter.budget import check_and_alert
        import tracker.db as dbmod

        tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = os.path.join(tempdir.name, "test.db")
        original_db = str(dbmod.DB_PATH)
        dbmod.DB_PATH = db_path
        dbmod._pool = None

        try:
            from tracker.db import init_db, setup_budget
            await init_db()
            await setup_budget("alert-test", daily=10.0, monthly=100.0)

            warnings = await check_and_alert("alert-test")
            assert isinstance(warnings, list)
        finally:
            dbmod.DB_PATH = original_db
            dbmod._pool = None

    @pytest.mark.asyncio
    async def test_check_and_alert_exceeded(self):
        from alerter.budget import check_and_alert
        import tracker.db as dbmod

        tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = os.path.join(tempdir.name, "test.db")
        original_db = str(dbmod.DB_PATH)
        dbmod.DB_PATH = db_path
        dbmod._pool = None

        try:
            from tracker.db import init_db, setup_budget, log_call
            await init_db()
            await setup_budget("over-budget", daily=0.001, monthly=100.0)

            # log a call that exceeds daily budget
            await log_call(model="gpt-4o", endpoint="/v1", input_tokens=1000000,
                          output_tokens=1000000, cost_usd=999.0,
                          latency_ms=100, project="over-budget",
                          request_id="r1", error_msg="", status_code=200)

            warnings = await check_and_alert("over-budget")
            assert isinstance(warnings, list)
        finally:
            dbmod.DB_PATH = original_db
            dbmod._pool = None


# ============================================================
# Forwarder Tests
# ============================================================

class TestForwarder:

    def test_get_model_from_body(self):
        from proxy.forwarder import _get_model
        body = b'{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'
        assert _get_model(body) == "gpt-4o"

    def test_get_model_missing(self):
        from proxy.forwarder import _get_model
        assert _get_model(b'{"messages":[]}') == ""

    def test_get_model_invalid_json(self):
        from proxy.forwarder import _get_model
        assert _get_model(b'not json') == ""

    def test_is_stream_true(self):
        from proxy.forwarder import _is_stream
        body = b'{"model":"gpt-4o","stream":true}'
        assert _is_stream(body) is True

    def test_is_stream_false(self):
        from proxy.forwarder import _is_stream
        body = b'{"model":"gpt-4o"}'
        assert _is_stream(body) is False

    def test_is_stream_invalid(self):
        from proxy.forwarder import _is_stream
        assert _is_stream(b'bad data') is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
