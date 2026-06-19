# Changelog

## [0.3.0] - 2026-06-19

### Changed
- Simplified config: PRICING dict, calculate_cost function
- Async SQLite with connection pooling (WAL mode)
- Admin token auth for /sentinel/* endpoints
- Path whitelist for proxy (ALLOWED_PREFIXES)
- Input validation for project names
- Streamlined forwarder with error handling
- Removed pydantic and python-dotenv dependencies

## [0.2.0] - 2026-06-17

### Added
- CSV export endpoint (`/sentinel/export/csv`)
- Model cost comparison endpoint (`/sentinel/compare`)
- Slack webhook budget alerts
- `SENTINEL_WEBHOOK_URL` environment variable for webhook configuration
- README_zh.md Chinese documentation

### Changed
- Updated README roadmap to reflect completed features

## [0.1.0] - 2026-06-16

### Added
- Initial release
- Transparent OpenAI-compatible proxy (`/v1/*`)
- Automatic token counting per request
- Built-in pricing for 20+ models
- SQLite storage (zero external dependencies)
- Streaming SSE passthrough
- Project tagging for team cost tracking
- Budget management with daily/monthly caps
- Spring Boot + Chart.js visualization dashboard
