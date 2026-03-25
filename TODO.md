# Longlist — Task Tracker

_Last updated: 2026-03-25_

## Completed

- [x] Rewrite `job_store.py` for PostgreSQL + SQLite dual backend
- [x] Add `psycopg2-binary` to requirements.txt
- [x] Fix `excel_generator.py` — match actual OpenRegister API response structure
- [x] Change empty field display from "n/v" to blank cells
- [x] Fix Stripe webhook secret mismatch (`.env.local` updated)
- [x] Create `/danke` and `/abgebrochen` Stripe redirect pages in `main.py`
- [x] Update `config.py` tier names: basis / kontakt / deep_data
- [x] Update `stripe_handler.py` for new tier names
- [x] Create branded HTML email templates (`email_html.py`)
- [x] Create Sales Deck (PPTX) — 7-slide German presentation
- [x] Update Financial Model Excel (Kontakt credits, margins)
- [x] Fix email bold formatting — `**text**` now renders as `<strong>` in HTML emails
- [x] Add document links column to Excel output (from OpenRegister details.documents)
- [x] Update `pipeline.py` to persist enriched_data and pipeline_result in job store
- [x] Create `CLAUDE.md` project memory file
- [x] Create `TODO.md` task tracker

## Ready to Deploy

- [ ] **Provision Railway PostgreSQL** — Run `railway add --plugin postgresql` or add via Dashboard, then set `DATABASE_URL` env var
- [ ] **Push all code changes to GitHub** — Files changed: config.py, email_html.py, email_writer.py, excel_generator.py, main.py, stripe_handler.py, job_store.py, pipeline.py, requirements.txt, CLAUDE.md, TODO.md
- [ ] **Redeploy to Railway** with PostgreSQL support
- [ ] **End-to-end verification** — Send test briefing, verify payment flow, check Excel output

## Backlog

- [ ] **Connect longlist.email domain** — GoDaddy DNS → Vercel for frontend, update STRIPE_SUCCESS_URL/CANCEL_URL to point to longlist.email/danke etc.
- [ ] **Archive old Stripe products** — 9 legacy products with outdated tier names/prices (manual via Stripe Dashboard, MCP lacks archive tool)
- [ ] **Verify OpenRegister document URL structure** — Make a live API call to confirm the exact format of `details.documents[]` entries, adjust `_extract_documents()` if needed
- [ ] **Excel document links as clickable hyperlinks** — Currently plain text; could use openpyxl `HYPERLINK()` formula for click-to-open
- [ ] **Add KI-Scoring column** — Mentioned in Basis tier description but not yet implemented in pipeline/Excel
- [ ] **Rate limiting / retry logic** — OpenRegister API might rate-limit on large batches; add exponential backoff
- [ ] **Email delivery confirmation** — Track whether delivery emails were actually received
- [ ] **Admin dashboard** — Web UI to view jobs, resend emails, monitor pipeline status
- [ ] **Automated tests** — Unit tests for excel_generator, email_html, job_store; integration tests for pipeline
- [ ] **Monitoring / alerting** — Pipeline failure alerts via Telegram or email
- [ ] **Volume discounts** — Pricing tiers for large orders (100+ companies)
- [ ] **Multi-language support** — English email templates for international clients
