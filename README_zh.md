# AI Cost Sentinel 💰

**轻量级 AI API 成本追踪代理 — 不改一行代码，透明拦截并统计每次 API 调用。**

支持所有 OpenAI 兼容 API（OpenAI / DeepSeek / 通义千问 / 智谱 等）。自动记录每次请求的 Token 消耗和费用，内置实时仪表盘。

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![Java](https://img.shields.io/badge/java-21-orange.svg)](https://adoptium.net/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Category](https://img.shields.io/badge/category-llm--cost%20|%20api--proxy%20|%20token--tracking%20|%20finops-orange)

> 💰 **LLM 成本追踪 · Token 监控 · API 代理 · AI FinOps**

> [English](README.md)

## 一行集成

**你唯一需要改的：** 把 `base_url` 指向代理地址，搞定。

```diff
- client = OpenAI(base_url="https://api.openai.com/v1", api_key="sk-xxx")
+ client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
```

代理透明转发请求、记录 Token 用量、计算费用——你的业务代码完全不动。

## 架构

```
你的应用 ──→ sentinel-proxy (:8000) ──→ 上游 AI API
                  │
                  ├── SQLite（调用记录 + 预算）
                  │
                  └── sentinel-dashboard (:9090) ──→ Web 仪表盘
```

## 快速开始

### 1. 启动代理

```bash
cd sentinel-proxy
pip install -r requirements.txt

# 可选：设置上游 API
export UPSTREAM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

python main.py  # → http://localhost:8000
```

### 2. 把应用指向代理

```python
client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
# 其他代码完全不变——SDK、方法、参数
```

### 3. 仪表盘（可选）

```bash
cd sentinel-dashboard
mvn spring-boot:run   # → http://localhost:9090
```

## 功能

| 功能 | 描述 |
|------|------|
| 🔍 **透明代理** | 不改 SDK，不改代码——只改 base_url |
| 📊 **Token 统计** | 自动记录每次调用的输入/输出 Token |
| 💰 **费用计算** | 内置 20+ 模型定价，自动换算 USD |
| 📈 **预算管理** | 设置日/月预算，超支告警 |
| 🌊 **流式支持** | 完整 SSE 透传 |
| 📉 **可视化仪表盘** | 费用趋势、模型分布、调用记录 |
| 💾 **零依赖存储** | SQLite——无需外部数据库 |
| 🏷️ **项目标签** | 按项目追踪费用，适合团队使用 |
| 📥 **CSV 导出** | 一键导出调用记录 |
| 🔔 **Webhook 告警** | 预算超支自动发送 Slack 通知 |

## API 端点

| 端点 | 描述 |
|------|------|
| `/v1/*` | 透明代理——转发所有 OpenAI 兼容请求 |
| `GET /sentinel/health` | 健康检查 |
| `GET /sentinel/stats?project=&days=30` | 综合统计（按模型、按日） |
| `GET /sentinel/calls?limit=50` | 最近调用记录 |
| `GET /sentinel/budget?project=` | 预算状态 |
| `POST /sentinel/budget?project=&daily=&monthly=` | 设置预算告警 |
| `GET /sentinel/export/csv?project=&days=30` | 导出 CSV |
| `GET /sentinel/compare?project=&days=30` | 模型成本效率对比 |

## 支持的模型与定价

| 模型 | 输入 /1M tokens | 输出 /1M tokens |
|-------|:-----------------:|:------------------:|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4-turbo | $10.00 | $30.00 |
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-haiku-4-5 | $0.80 | $4.00 |
| claude-opus-4-7 | $15.00 | $75.00 |
| deepseek-chat | $0.27 | $1.10 |
| deepseek-reasoner | $0.55 | $2.19 |
| qwen-plus | $0.80 | $2.80 |
| qwen-turbo | $0.30 | $0.60 |
| qwen-max | $2.40 | $9.60 |

> 在 `sentinel-proxy/config.py` → `MODEL_PRICING` 中添加更多模型。

## Docker

```bash
docker-compose up -d
# 代理: http://localhost:8000
# 仪表盘: http://localhost:9090
```

## 项目结构

```
ai-cost-sentinel/
├── sentinel-proxy/          # Python FastAPI 代理
│   ├── main.py              # 入口，路由注册
│   ├── config.py            # 定价表，配置
│   ├── proxy/
│   │   └── forwarder.py     # 请求转发 + 费用计算
│   ├── tracker/
│   │   └── db.py            # SQLite 数据库操作
│   ├── alerter/
│   │   └── budget.py        # 预算告警 + Webhook
│   └── requirements.txt
├── sentinel-dashboard/      # Java Spring Boot 仪表盘
│   ├── pom.xml
│   └── src/main/java/com/costsentinel/
├── tests/
│   └── test_sentinel.py
├── docker-compose.yml
└── README.md
```

## 与 PromptSlim 配合

**调用前瘦身 → 调用中追踪。** 完整的成本优化闭环。

> 详见 [promptslim](https://github.com/JING04-PRODUCER/promptslim)

## 路线图

- [x] CSV 导出
- [x] 模型成本对比
- [x] Slack / 企业微信 Webhook 告警
- [ ] Grafana 仪表盘模板
- [ ] 多用户/团队支持
- [ ] InfluxDB 导出

## 许可证

MIT — 详见 [LICENSE](LICENSE)
