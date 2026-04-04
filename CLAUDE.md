# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Longlist?

Longlist is an email-based Research-as-a-Service for German M&A advisors. Clients send a research briefing via email, receive a structured offer with Stripe payment links, and after payment get an enriched Excel longlist of companies — all automated.

**URL:** https://longlist.email (frontend on Vercel) / https://longlist-production.up.railway.app (backend API)

**Owner:** Max Zwisler (maximzwisler@gmail.com)

## Commands

```bash
# Run locally
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -q

# Run a single test
pytest tests/test_job_store.py -q
```

Production uses `Procfile`: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### CLI Tools

```bash
brew install railway                      # Railway deployment
brew install stripe/stripe-cli/stripe     # Stripe CLI
brew install gh                           # GitHub CLI
npm i -g vercel                           # Vercel CLI
```

## Architecture

```
Client Email → AgentMail Webhook → Claude AI (parse briefing + confidence score)
  → Confidence >= 0.95: Direct processing (existing flow)
  → Confidence < 0.95: Smart Service Menu email → User clicks CTA → Processing
  → Attachment detected: Menu with "Firmenliste anreichern" highlighted
  → OpenRegister Search (preview) → Stripe Checkout Links
  → Reply with offer email → Client pays via Stripe
  → Stripe Webhook → Pipeline: enrich all companies via OpenRegister
  → Generate Excel → Send delivery email with attachment
```

### Tech Stack
- **Backend:** FastAPI + uvicorn, Python 3.12, hosted on Railway
- **Database:** PostgreSQL (production via Railway) / SQLite (local dev fallback)
- **AI:** Anthropic Claude API (briefing parsing, email writing)
- **Company Data:** OpenRegister SDK (German Handelsregister API)
- **Payments:** Stripe Checkout (dynamic per-company pricing)
- **Email:** AgentMail SDK (send/receive emails)
- **Email Lookup:** Anymailfinder (GF email for Deep Data tier)
- **Frontend:** Vercel (static landing page at longlist.email)

### Railway Deployment
- Project: `heroic-alignment`, Service: `longlist`
- Production URL: `longlist-production.up.railway.app`
- Needs `DATABASE_URL` env var set to Railway PostgreSQL connection string

## Package Tiers & Excel Columns (aligned with longlist.email)

| Package | Price/Company | OpenRegister Endpoints | Credits | Extras |
|---------|--------------|----------------------|---------|--------|
| **Basis** | 1,50 € | details | 10 | KI-Scoring |
| **Kontakt** | 2,50 € | details, owners | 20 | Gesellschafterstruktur |
| **Deep Data** | 4,00 € | details, financials, owners, ubos, holdings | 65 | Finanzen, UBOs, Beteiligungen, GF-Email |

### Excel Columns per Tier

**All tiers (from Details endpoint):**
Nr., Firma, Rechtsform, Handelsregister, Adresse, PLZ, Stadt, Geschäftsführer, Website, Telefon, E-Mail, Stammkapital, Branche (WZ-Code), Unternehmensgegenstand, Status, Gründungsdatum, Dokumente (Links)

**Kontakt adds:** Gesellschafter, Beteiligung (%)

**Deep Data adds:** Umsatz (EUR), Bilanzsumme (EUR), Eigenkapital (EUR), Mitarbeiter, Geschäftsjahr, Gesellschafter, Beteiligung (%), Wirtsch. Berechtigte (UBOs), Beteiligungen/Töchter, GF-Email

**Rule:** All columns for a tier are ALWAYS shown, even if data is empty (blank cells, never "n/v").

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, all routes, webhooks, /danke + /abgebrochen pages |
| `config.py` | Environment vars, PACKAGES tier config |
| `job_store.py` | Dual-backend persistence: PostgreSQL (prod) + SQLite (dev) |
| `pipeline.py` | Enrichment pipeline: search → enrich → Excel → persist |
| `excel_generator.py` | openpyxl Excel generation with German formatting |
| `openregister_client.py` | Async/sync OpenRegister API wrapper |
| `stripe_handler.py` | Stripe Checkout session creation |
| `email_html.py` | Branded HTML email templates |
| `email_writer.py` | Claude AI email composition |
| `anymailfinder_client.py` | GF email lookup |
| `preview_search.py` | OpenRegister company search for preview |
| `briefing_parser.py` | Claude AI briefing parsing |
| `attachment_parser.py` | Excel/CSV attachment parsing for file upload enrichment |
| `USER_FLOWS.md` | Flow visualization and service routing documentation |

## OpenRegister API (IMPORTANT)

### Response Structure Gotchas
- `details.name` is a **dict**: `{"name": "Firma GmbH", "legal_form": "gmbh"}` — NOT a string
- Address uses `postal_code` (not `zip_code`), `street` includes house number
- Contact uses `website_url` (not `website`)
- Owners use `percentage_share` (not `share_percent`), with nested `legal_person`/`natural_person`
- `details.indicators[]` list contains financial summaries (revenue, balance_sheet_total, equity, employees, date)
- `details.documents[]` list contains document references with URLs
- Details endpoint (10 credits) already includes contact data — no separate contact endpoint needed

### Search API (verified 2026-04-04 with 33 live queries)
- **`query` is the most important parameter** — searches company names, broadest results
- **Safe filters:** `status=active`, `legal_form`, `location`, `incorporated_at`
- **Moderate filters:** `has_representative_owner`, `youngest_owner_age`, `is_family_owned`
- **NEVER use as filters:** `employees` (2% coverage!), `industry_codes` (unreliable WZ codes), `revenue`, `balance_sheet_total`
- **Max 3 filters** — each filter roughly halves results
- See `ARCHITECTURE.md` for full verified search behavior

## Database Schema (PostgreSQL)

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'parsing',
    sender TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    service_type TEXT NOT NULL DEFAULT '',
    package TEXT NOT NULL DEFAULT '',
    thread_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    total_companies INTEGER NOT NULL DEFAULT 0,
    parsed JSONB NOT NULL DEFAULT '{}',
    preview JSONB NOT NULL DEFAULT '{}',
    payment_urls JSONB NOT NULL DEFAULT '{}',
    pipeline_result JSONB NOT NULL DEFAULT '{}',
    enriched_data JSONB NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    extra JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Indexes on: `sender`, `status`, `created_at DESC`

## Brand Design Tokens

- Primary: `#1b4332` (dark green)
- Background: `#faf9f6`
- Display font: Georgia (substitute for Fraunces)
- Body font: Calibri / Helvetica Neue
- Border subtle: `rgba(24,24,27,0.08)`

## Environment Variables

Required:
- `ANTHROPIC_API_KEY` — Claude API
- `OPENREGISTER_API_KEY` — Company data API
- `DATABASE_URL` — PostgreSQL connection (production)
- `STRIPE_SECRET_KEY` — Stripe payments
- `STRIPE_WEBHOOK_SECRET` — Stripe webhook verification
- `AGENTMAIL_API_KEY` — Email service
- `AGENTMAIL_FROM` — Sender address (briefing-mandatscout@agentmail.to)

Optional:
- `ANYMAILFINDER_API_KEY` — GF email lookup (Deep Data)
- `LONGLIST_ADMIN_TOKEN` — Admin API auth
- `DATABASE_PATH` — SQLite path for local dev (default: longlist.db)
- `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` — Redirect URLs

## Job Status Flow

```
parsing → awaiting_service_selection → service_selected → preview_done → offer_sent → paid → enriched → excel_ready → delivered
parsing → preview_done → offer_sent → ... (high-confidence skip, >= 0.95)
                       → no_results (0 Treffer → Rückfrage gesendet)
                       → error (if failure)
```

- `awaiting_service_selection` — Smart Service Menu sent, waiting for user to click a CTA
- `service_selected` — User clicked a service button, processing continues

## Service Routing

**Currently only `longlist` is active.** Other service types (enrichment, sell_side, file_enrichment) are disabled while we focus on search quality. The code is preserved for future re-activation.

All incoming briefings are routed directly to Longlist-Recherche processing (no Smart Service Menu).

## Important Decisions

1. **Empty cells instead of "n/v"** — When data is not available, leave cells blank (not "n/v" or "N/A")
2. **Documents always included** — Document links column is shown in all packages since details endpoint always returns them
3. **Enriched data persisted** — Pipeline stores `enriched_data` JSONB in job for redelivery without re-fetching
4. **Dual DB backend** — job_store.py auto-detects PostgreSQL via `DATABASE_URL` env var, falls back to SQLite
5. **Dynamic Stripe pricing** — Uses `price_data` with `product_data` per checkout, not pre-created prices
6. **All email text in German** — Target audience is German M&A advisors
