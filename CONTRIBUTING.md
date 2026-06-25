# Contributing to AI Cost Sentinel

## Getting Started

```bash
git clone https://github.com/JING04-PRODUCER/ai-cost-sentinel.git
cd ai-cost-sentinel

# Proxy (Python)
cd sentinel-proxy
pip install -r requirements.txt

# Dashboard (Streamlit)
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

## Development

```bash
# Run mock tests (no API key needed)
python tests/test_mock.py

# Run integration tests (needs API key)
python tests/test_sentinel.py
```

## Adding Model Pricing

Add entries to `PRICING` in `sentinel-proxy/config.py`:

```python
"model-id": (input_price, output_price)  # per 1M tokens
```

## Pull Request

1. Update CHANGELOG.md
2. Ensure tests pass
3. Describe what and why in the PR description
