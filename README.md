# AI Cost Sentinel

一个 API 代理，架在你应用和 AI 服务之间，自动记录每次调用的 Token 消耗和费用。不用改业务代码，不用接 SDK，只改一行 `base_url`。

支持 OpenAI、DeepSeek、Qwen、智谱等等所有 OpenAI 兼容接口。

[![CI](https://github.com/JING04-PRODUCER/ai-cost-sentinel/actions/workflows/python-test.yml/badge.svg)](https://github.com/JING04-PRODUCER/ai-cost-sentinel/actions/workflows/python-test.yml)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 怎么用

一共就两步。

启动代理：

```bash
cd sentinel-proxy
pip install -r requirements.txt
python main.py   # 跑在 :8000
```

然后把代码里的 `base_url` 改一下：

```diff
- client = OpenAI(base_url="https://api.openai.com/v1", api_key="sk-xxx")
+ client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
```

完事。之后每次调用都会被记录——用了多少 Token、花了多少钱，全能看到。

## 有什么功能

- 代理透明转发，你的代码不用动
- 自动算 Token 消耗和费用，内置了 20+ 模型的定价表
- 可以设日/月预算，超了自动拦截或者通知
- 流式响应也支持，SSE 完整透传
- 按项目追踪成本（在请求头里加 `x-sentinel-project`）
- 自带 Streamlit 仪表盘，看趋势和分布

```bash
# 看统计
curl http://localhost:8000/sentinel/stats?days=30

# 设预算
curl -X POST "http://localhost:8000/sentinel/budget?project=myapp&daily=10&monthly=200"

# 导出 CSV
curl "http://localhost:8000/sentinel/export/csv?project=myapp&days=30" > costs.csv
```

仪表盘单独启动：

```bash
pip install streamlit pandas plotly
streamlit run dashboard/app.py   # → :8501
```

## 定价参考

| 模型 | 输入 /1M | 输出 /1M |
|------|:------:|:------:|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-haiku-4-5 | $0.80 | $4.00 |
| claude-opus-4-7 | $15.00 | $75.00 |
| deepseek-chat | $0.27 | $1.10 |
| qwen-plus | $0.80 | $2.80 |
| qwen-turbo | $0.30 | $0.60 |

更多模型在 `sentinel-proxy/config.py` 里加。

## 架构

```
你的应用 → sentinel-proxy (:8000) → 上游 AI API
                ↓
         SQLite（调用记录 + 预算配置）
                ↓
    Streamlit 仪表盘 (:8501)
```

## 已知限制

- SQLite 不适合高并发，日均十万次以内够用，超了换 PostgreSQL
- 定价表在代码里写死的，API 调价需要手动改
- 仪表盘要单独起一条命令

## License

MIT
