# Contributing to AI Cost Sentinel

## Getting Started

```bash
git clone https://github.com/JING04-PRODUCER/ai-cost-sentinel.git
cd ai-cost-sentinel

# Proxy (Python)
cd sentinel-proxy
pip install -r requirements.txt

# Dashboard (Java)
cd sentinel-dashboard
./mvnw spring-boot:run
```

## Development

```bash
# Run proxy tests
python tests/test_sentinel.py

# Java tests
cd sentinel-dashboard && ./mvnw test
```

## Adding Model Pricing

Add entries to `PRICING` in `sentinel-proxy/config.py`:

```python
"model-id": {"input": 0.00, "output": 0.00}  # per 1M tokens
```

## Pull Request

1. Update CHANGELOG.md
2. Ensure tests pass
3. Describe what and why in the PR description
