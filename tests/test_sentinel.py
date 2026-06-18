"""
AI Cost Sentinel 集成测试

测试通过代理调用真实 API（百炼 qwen-plus）
"""

from __future__ import annotations

import os
import sys
import json
import time
import pytest
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sentinel-proxy"))

# 百炼 API 配置（从环境变量读取，不硬编码密钥）
BAILIAN_KEY = os.environ.get("BAILIAN_API_KEY", "")
BAILIAN_BASE = os.environ.get("BAILIAN_BASE_URL", "https://ws-eq9tcvlhw5m65ftm.cn-beijing.maas.aliyuncs.com/compatible-mode")

# 如果未设置环境变量，跳过需要真实 API 调用的测试
NEEDS_REAL_API = bool(BAILIAN_KEY)

# 代理地址
PROXY_BASE = "http://localhost:8000"


def get_client(via_proxy: bool = True):
    """创建 OpenAI 客户端"""
    if via_proxy:
        return OpenAI(api_key=BAILIAN_KEY, base_url=f"{PROXY_BASE}/v1")
    else:
        return OpenAI(api_key=BAILIAN_KEY, base_url=f"{BAILIAN_BASE}/v1")


class TestProxy:
    """代理功能测试"""

    def test_health_check(self):
        """测试健康检查"""
        import httpx
        resp = httpx.get(f"{PROXY_BASE}/sentinel/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_normal_chat(self):
        """测试普通对话 — 应该正常返回 + 被记录"""
        client = get_client(via_proxy=True)
        resp = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": "1+1=?"}],
            temperature=0,
            max_tokens=50,
        )
        assert resp.choices[0].message.content is not None
        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0

    def test_streaming_chat(self):
        """测试流式对话"""
        client = get_client(via_proxy=True)
        stream = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": "说hello"}],
            stream=True,
            max_tokens=20,
        )
        chunks = list(stream)
        assert len(chunks) > 0

    def test_stats_endpoint(self):
        """测试统计接口"""
        client = get_client(via_proxy=True)
        # 先发几个请求
        for _ in range(2):
            client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )

        time.sleep(0.5)

        import httpx
        resp = httpx.get(f"{PROXY_BASE}/sentinel/stats?project=default&days=1")
        data = resp.json()
        assert "by_model" in data
        assert "by_day" in data
        assert "budget" in data

    def test_recent_calls(self):
        """测试调用记录"""
        import httpx
        resp = httpx.get(f"{PROXY_BASE}/sentinel/calls?limit=5")
        data = resp.json()
        assert "calls" in data
        assert len(data["calls"]) > 0
        call = data["calls"][0]
        assert "model" in call
        assert "cost_usd" in call
        assert "input_tokens" in call

    def test_budget_api(self):
        """测试预算管理"""
        import httpx
        # 设置预算
        resp = httpx.post(
            f"{PROXY_BASE}/sentinel/budget",
            params={"project": "test-proj", "daily": 10.0, "monthly": 100.0},
        )
        assert resp.status_code == 200

        # 查询预算
        resp = httpx.get(f"{PROXY_BASE}/sentinel/budget?project=test-proj")
        data = resp.json()
        assert data["daily_limit"] == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
