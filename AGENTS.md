<!-- Generated: 2026-04-04 | Updated: 2026-04-04 -->

# Longlist

## Purpose
Email-based Research-as-a-Service for German M&A advisors. Clients send a research briefing via email, receive a structured offer with Stripe payment links, and after payment get an enriched Excel longlist of companies — fully automated.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI app — all routes, webhooks, /danke + /abgebrochen pages (largest file) |
| `config.py` | Environment vars, PACKAGES tier config (Basis/Kontakt/Deep Data) |
| `job_store.py` | Dual-backend persistence: PostgreSQL (prod) + SQLite (dev) |
| `pipeline.py` | Enrichment pipeline: search → enrich → Excel → persist |
| `excel_generator.py` | openpyxl Excel generation with German formatting |
| `openregister_client.py` | Async/sync OpenRegister API wrapper (German Handelsregister) |
| `stripe_handler.py` | Stripe Checkout session creation with dynamic pricing |
| `email_html.py` | Branded HTML email templates |
| `email_writer.py` | Claude AI email composition |
| `briefing_parser.py` | Claude AI briefing parsing with confidence scoring |
| `attachment_parser.py` | Excel/CSV attachment parsing for file upload enrichment |
| `agentmail_client.py` | AgentMail send/receive wrapper |
| `agentmail_inbound.py` | Inbound email webhook handler |
| `anymailfinder_client.py` | GF email lookup for Deep Data tier |
| `preview_search.py` | OpenRegister company search for preview |
| `ai_client.py` | Anthropic Claude API client |
| `r2_client.py` | Cloudflare R2 storage client |
| `sell_side_emails.py` | Sell-side M&A email templates |
| `sell_side_excel.py` | Sell-side Excel generation |
| `sell_side_pipeline.py` | Sell-side buyer longlist pipeline |
| `buyer_groups.py` | Buyer group definitions and matching |
| `buyer_group_optimizer.py` | AI-powered buyer group optimization |
| `benchmark_buyer_groups.py` | Buyer group benchmarking tool |
| `target_analyzer.py` | Target company analysis for sell-side |
| `telegram_notify.py` | Telegram notification client |
| `admin_auth.py` | Admin API authentication |
| `requirements.txt` | Python dependencies |
| `Procfile` | Railway deployment command |
| `runtime.txt` | Python version for Railway |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `tests/` | pytest test suite (see `tests/AGENTS.md`) |
| `buyer-research/` | Separate buyer research sub-app for sell-side M&A (see `buyer-research/AGENTS.md`) |
| `skills/` | Claude Code skills (stripe-best-practices, upgrade-stripe) |

## For AI Agents

### Working In This Directory
- All email text and user-facing strings are in **German** — target audience is German M&A advisors
- Empty cells instead of "n/v" or "N/A" in Excel output — leave blank when data is missing
- OpenRegister API has non-obvious response structures:
  - `details.name` is a **dict** `{"name": "...", "legal_form": "..."}`, NOT a string
  - Address uses `postal_code` (not `zip_code`), `street` includes house number
  - Contact uses `website_url` (not `website`)
  - Owners use `percentage_share` (not `share_percent`), with nested `legal_person`/`natural_person`
- Dual DB backend: auto-detects PostgreSQL via `DATABASE_URL` env var, falls back to SQLite
- Dynamic Stripe pricing uses `price_data` with `product_data`, not pre-created prices
- Only `longlist` service is active — other services (enrichment, sell_side, file_enrichment) disabled

### Testing Requirements
- Run all tests: `pytest tests/ -q`
- Run single test: `pytest tests/test_job_store.py -q`
- Run locally: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

### Common Patterns
- Job status flow: `parsing → awaiting_service_selection → service_selected → preview_done → offer_sent → paid → enriched → excel_ready → delivered`
- Only `longlist` service active (enrichment, sell_side, file_enrichment disabled)
- 3 pricing tiers: Basis (1.50€), Kontakt (2.50€), Deep Data (4.00€)

## Dependencies

### External
- `fastapi` + `uvicorn` — Web framework
- `anthropic` — Claude AI for briefing parsing and email writing
- `openregister-sdk` — German Handelsregister company data
- `stripe` — Payment processing
- `agentmail` — Email send/receive
- `openpyxl` — Excel generation
- `httpx` — Async HTTP client
- `psycopg2-binary` — PostgreSQL driver
- `boto3` — Cloudflare R2 storage
- `tavily-python` — Web search for research

<!-- MANUAL: -->
