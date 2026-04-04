<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-04 | Updated: 2026-04-04 -->

# tests

## Purpose
pytest test suite covering the core Longlist service — webhooks, persistence, parsing, payments, and routing logic.

## Key Files

| File | Description |
|------|-------------|
| `conftest.py` | Shared fixtures (test client, mock jobs, etc.) |
| `test_admin_auth.py` | Admin token authentication |
| `test_agentmail_inbound.py` | Inbound email webhook processing |
| `test_attachment_parser.py` | Excel/CSV attachment parsing |
| `test_job_store.py` | Job persistence across PostgreSQL/SQLite backends |
| `test_main_health.py` | Health check endpoint |
| `test_smart_menu.py` | Smart Service Menu confidence routing |
| `test_stripe_handler.py` | Stripe checkout session creation and webhooks |

## For AI Agents

### Working In This Directory
- Tests use **SQLite backend** (no `DATABASE_URL` set in test env)
- Use `pytest-asyncio` for async test functions
- Mock external APIs (OpenRegister, Stripe, AgentMail, Claude) — don't make real calls
- Test file naming: `test_{module_name}.py`

### Testing Requirements
- Run all: `pytest tests/ -q`
- Run single: `pytest tests/test_job_store.py -q`
- Add tests when modifying core pipeline, webhook, or payment logic

### Common Patterns
- FastAPI `TestClient` for endpoint tests
- Fixtures in `conftest.py` for reusable test data
- Assert German-language strings in email/response tests

## Dependencies

### Internal
- All root-level Python modules being tested

### External
- `pytest` >= 8.0
- `pytest-asyncio` >= 0.24

<!-- MANUAL: -->
