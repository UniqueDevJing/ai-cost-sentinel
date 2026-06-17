# AI Cost Sentinel

轻量 AI API 成本追踪代理 — **一行代码不改，透明拦截统计**。

支持所有 OpenAI 兼容 API（OpenAI / 百炼 / DeepSeek / 智谱 等），自动记录每次调用的 Token 消耗和费用，提供实时仪表盘。

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

# 安装依赖
pip install -r requirements.txt

# 配置上游 API（可选，默认从请求头自动识别）
export UPSTREAM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 启动代理
python main.py
```

代理启动在 `http://localhost:8000`。

### 2. 修改你的 API 调用

原来的代码：
```python
client = OpenAI(base_url="https://api.openai.com/v1", api_key="sk-xxx")
```

改为：
```python
client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
```

**就改一个 URL，完全透明**。代理会自动转发、记录 Token 消耗、计算费用。

### 3. 启动仪表盘（可选）

```bash
cd sentinel-dashboard

# 确认 application.yml 中 proxy-url 指向代理
mvn spring-boot:run
```

打开 `http://localhost:9090` 查看实时仪表盘。

## 功能

- **透明代理** — 不改业务代码，不改 SDK，只改 base_url
- **Token 计数** — 自动记录每次调用的输入/输出 Token
- **费用计算** — 内置主流模型定价，自动换算 USD
- **预算管理** — 设置日/月预算，超支告警
- **流式支持** — 完整透传 SSE 流式响应
- **可视化仪表盘** — 费用趋势、模型分布、调用历史
- **零依赖存储** — SQLite，无需额外数据库

## API 端点

| 端点 | 说明 |
|------|------|
| `/v1/*` | 透明代理，转发所有 OpenAI 兼容请求 |
| `GET /sentinel/health` | 健康检查 |
| `GET /sentinel/stats?project=&days=30` | 综合统计（按模型/按日） |
| `GET /sentinel/calls?limit=50` | 最近调用记录 |
| `GET /sentinel/budget?project=` | 预算状态 |
| `POST /sentinel/budget?project=&daily=&monthly=` | 设置预算 |

## 内置模型定价

| 模型 | 输入/1M tokens | 输出/1M tokens |
|------|---------------|----------------|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4-turbo | $10.00 | $30.00 |
| claude-3.5-sonnet | $3.00 | $15.00 |
| deepseek-chat | $0.14 | $0.28 |
| deepseek-reasoner | $0.55 | $2.19 |
| qwen-plus | $0.80 | $2.00 |
| qwen-turbo | $0.30 | $0.60 |
| qwen-max | $2.40 | $9.60 |

可在 `sentinel-proxy/config.py` 的 `MODEL_PRICING` 中添加更多模型。

## Docker 部署

```bash
docker-compose up -d
```

- 代理: `http://localhost:8000`
- 仪表盘: `http://localhost:9090`

## 项目结构

```
ai-cost-sentinel/
├── sentinel-proxy/          # Python FastAPI 代理
│   ├── main.py              # 入口，路由注册
│   ├── config.py            # 定价表、配置
│   ├── proxy/
│   │   └── forwarder.py     # 请求转发 + 费用计算
│   ├── tracker/
│   │   └── db.py            # SQLite 数据库操作
│   ├── alerter/
│   │   └── budget.py        # 预算告警
│   └── requirements.txt
├── sentinel-dashboard/      # Java Spring Boot 仪表盘
│   ├── pom.xml
│   └── src/main/java/com/costsentinel/
│       ├── Application.java
│       ├── config/AppConfig.java
│       └── controller/
│           ├── DashboardController.java
│           └── ApiController.java
├── tests/                   # 集成测试
│   └── test_sentinel.py
├── docker-compose.yml
└── README.md
```

## License

MIT
