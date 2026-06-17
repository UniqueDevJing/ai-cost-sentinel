"""
AI Cost Sentinel 配置

通过环境变量 / .env 文件配置。
优先级：环境变量 > .env > 默认值
"""

import os
from pathlib import Path


# --- 文件路径 ---
BASE_DIR = Path(__file__).parent
DB_PATH = os.getenv("SENTINEL_DB_PATH", str(BASE_DIR / "sentinel.db"))


# --- 代理配置 ---
PROXY_PORT = int(os.getenv("SENTINEL_PORT", "8000"))
PROXY_HOST = os.getenv("SENTINEL_HOST", "0.0.0.0")


# --- 上游 API 配置 ---
UPSTREAM_BASE_URL = os.getenv(
    "UPSTREAM_BASE_URL",
    "https://api.openai.com/v1"
).rstrip("/")

UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "")
UPSTREAM_TIMEOUT = int(os.getenv("UPSTREAM_TIMEOUT", "120"))


# --- 预算告警 ---
BUDGET_DAILY_LIMIT = float(os.getenv("SENTINEL_BUDGET_DAILY", "5.0"))  # 美元
BUDGET_MONTHLY_LIMIT = float(os.getenv("SENTINEL_BUDGET_MONTHLY", "50.0"))
ALERT_ENABLED = os.getenv("SENTINEL_ALERT_ENABLED", "true").lower() == "true"


# ============================================
# 模型定价表 (USD / 1M tokens)
# 数据来源：各厂商官方定价页，可自行扩展
# ============================================
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 10.00, "output": 40.00},

    # Anthropic (via OpenAI compatible proxy)
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},

    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},

    # 阿里百炼 (qwen)
    "qwen-plus": {"input": 0.0028, "output": 0.0084},  # 约 2元/1M tokens = $0.28/1M
    "qwen-max": {"input": 0.0056, "output": 0.0168},
    "qwen-turbo": {"input": 0.0008, "output": 0.0024},

    # 默认（未知模型）
    "default": {"input": 1.00, "output": 4.00},
}


def get_model_price(model: str) -> dict:
    """获取模型定价，找不到则返回默认值"""
    # 模糊匹配：gpt-4o-2024-08-06 → gpt-4o
    for key in MODEL_PRICING:
        if model.startswith(key):
            return MODEL_PRICING[key]
    return MODEL_PRICING["default"]


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """计算单次调用的费用 (USD)"""
    price = get_model_price(model)
    cost = (input_tokens / 1_000_000) * price["input"] + \
           (output_tokens / 1_000_000) * price["output"]
    return round(cost, 6)
