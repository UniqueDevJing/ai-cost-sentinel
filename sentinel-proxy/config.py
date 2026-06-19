"""配置"""

from __future__ import annotations
import os

UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "https://api.openai.com/v1")
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "")
UPSTREAM_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "120"))
ADMIN_TOKEN = os.getenv("SENTINEL_ADMIN_TOKEN", "")
WEBHOOK_URL = os.getenv("SENTINEL_WEBHOOK_URL", "")
BUDGET_MODE = os.getenv("SENTINEL_BUDGET_MODE", "notify_only")  # "reject" | "notify_only"

PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "qwen-plus": (0.80, 2.80),
    "qwen-turbo": (0.30, 0.60),
    "qwen-max": (2.40, 9.60),
    "default": (1.00, 3.00),
}


def calculate_cost(model: str, input_t: int, output_t: int) -> float:
    in_c, out_c = PRICING.get(model, PRICING["default"])
    return input_t * in_c / 1e6 + output_t * out_c / 1e6
