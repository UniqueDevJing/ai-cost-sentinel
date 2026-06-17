# AI Cost Sentinel

调 AI API 的时候想知道花了多少钱，做了这个。

## 它能干什么

改一行代码（把 API base_url 指向这个代理），之后的每次调用自动记录 Token 用量和费用，不用改 SDK，不用改业务逻辑。

本地 SQLite 存数据，不依赖外部数据库。超预算了会提醒你。另外写了个简单的 Web 仪表盘看趋势。

我在本地跑着，追踪自己调百炼 API 的开销。

## 怎么用

先把代理跑起来：

```bash
cd sentinel-proxy
pip install -r requirements.txt
python main.py   # 默认跑在 :8000
```

然后改代码里的 base_url：

```python
# 原来
client = OpenAI(base_url="https://api.openai.com/v1", api_key="sk-xxx")

# 改成
client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
```

之后每次调用，代理自动记录 Token 消耗和费用。仪表盘（可选）：

```bash
cd sentinel-dashboard
mvn spring-boot:run   # 跑在 :9090，浏览器打开看
```

Docker：`docker-compose up -d` 一次性全启动。

## 提供的 API

代理在 `/v1/*` 透明转发所有请求，额外提供几个管理端点：

- `GET /sentinel/health` — 健康检查
- `GET /sentinel/stats?project=&days=30` — 按模型和按日的费用统计
- `GET /sentinel/calls?limit=50` — 最近的调用记录
- `GET /sentinel/budget?project=` — 当前预算使用情况
- `POST /sentinel/budget?project=&daily=&monthly=` — 设置项目预算

## 定价表

内置了一些常用模型的价格，在 `sentinel-proxy/config.py` 里可以自己加：

gpt-4o ($2.50/$10.00)、gpt-4o-mini ($0.15/$0.60)、deepseek-chat ($0.27/$1.10)、qwen-plus ($0.0028/$0.0084) 等。

## 项目结构

```
sentinel-proxy/       # Python FastAPI 代理
  main.py             # 入口
  config.py           # 价格表、配置
  proxy/forwarder.py  # 请求转发和费用计算
  tracker/db.py       # SQLite 操作
  alerter/budget.py   # 预算告警
sentinel-dashboard/   # Java Spring Boot 仪表盘
tests/                # 6 个集成测试
```

## License

MIT
