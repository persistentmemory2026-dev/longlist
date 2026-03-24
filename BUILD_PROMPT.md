# LONGLIST — Build Prompt for Claude Desktop

You are building **Longlist**, an email-based Research-as-a-Service for German M&A advisors. The entire project goes in `/Users/clawdmandach/Documents/Railway-longlist-test/`.

## What Longlist Does

Client emails briefing@longlist.de → Claude parses briefing → OpenRegister API searches/enriches German companies → Client picks a data package → Pays via Stripe link in email → Pipeline enriches → Excel delivered via email.

**Zero UI. Email-only. 3 APIs + Claude.**

## The Flow

```
1. Email arrives (AgentMail webhook → POST /webhook/agentmail)
2. Claude Call #1: Parse briefing into structured JSON
3. IF Service 2 (Longlist): Run OpenRegister Advanced Filter Search (€0.10) to get count + preview
4. Reply email: "Wir haben X Unternehmen gefunden" + 3 Stripe payment links (BASIS/STANDARD/PREMIUM)
5. Client clicks link → pays on Stripe hosted checkout
6. Stripe webhook (POST /webhook/stripe) → triggers enrichment pipeline
7. Pipeline: OpenRegister endpoints per company → Anymailfinder email fallback → Excel generation
8. Telegram notification to Max for QA review
9. Claude Call #2: Write delivery email
10. AgentMail: Reply in same thread with Excel attachment
```

## Tech Stack

- **Runtime:** Python 3.12, FastAPI + uvicorn
- **Hosting:** Railway (always-on, $5/mo)
- **APIs:** OpenRegister (company data), Anthropic/Claude (intelligence), Stripe (payments), AgentMail (email), Anymailfinder (email lookup), Telegram Bot (QA alerts)
- **Excel:** openpyxl

## Stripe Products & Prices (ALREADY CREATED — LIVE)

```
Products:
  prod_UCz9mb4k78B5Ge  → Longlist BASIS
  prod_UCz9PLjUPCWJme  → Longlist STANDARD
  prod_UCz9d44tigbLa7  → Longlist PREMIUM

Prices (EUR, one-time):
  Enrichment (Service 1):
    BASIS    €149 → price_1TEZBNAhhBDA1IxVv0iofGpG
    STANDARD €249 → price_1TEZBWAhhBDA1IxV529sW8Bf
    PREMIUM  €399 → price_1TEZBdAhhBDA1IxVk4hFy662

  Longlist (Service 2):
    BASIS    €199 → price_1TEZBSAhhBDA1IxVHyb6TlKc
    STANDARD €299 → price_1TEZBZAhhBDA1IxVpPYQt5nP
    PREMIUM  €449 → price_1TEZBhAhhBDA1IxVmt7ed7UW
```

## Three Packages

| Package | Endpoints per company | Data |
|---------|----------------------|------|
| BASIS | Autocomplete + Details + Contact | Stammdaten, Adresse, GF, Website, Telefon |
| STANDARD | + Financials | + Umsatz, Bilanz, EK, Mitarbeiter |
| PREMIUM | + Owners + Anymailfinder | + Gesellschafter, verifizierte GF-Email |

## OpenRegister API — VERIFIED LIVE

Base URL: `https://api.openregister.de`
Auth: `Authorization: Bearer {OPENREGISTER_API_KEY}`
SDK: `pip install openregister` (from oregister/openregister-python)

**Critical SDK usage (tested & confirmed):**
```python
from openregister import Openregister, AsyncOpenregister

client = Openregister(api_key=OPENREGISTER_API_KEY)

# Advanced Filter Search — 10 credits per QUERY (not per result!)
result = client.search.find_companies_v1(
    query={"value": "Maschinenbau"},  # NOTE: query is a dict, not a string!
    filters=[
        {"field": "status", "value": "active"},
        {"field": "legal_form", "value": "gmbh"},
        {"field": "has_representative_owner", "value": "true"},  # ALL values must be strings!
        {"field": "youngest_owner_age", "min": "60"},
    ],
    location={"latitude": 48.5, "longitude": 10.5, "radius": 250.0},
    pagination={"page": 1, "per_page": 5}
)
# Returns: result.pagination.total_results (int), result.results (list of companies with name, company_id, etc.)

# Company Details — 10 credits
details = client.company.get_details_v1(company_id="DE-HRB-F1103-267645")

# Financials — 10 credits
financials = client.company.get_financials_v1(company_id="DE-HRB-F1103-267645")

# Owners — 10 credits
owners = client.company.get_owners_v1(company_id="DE-HRB-F1103-267645")

# Contact (web data) — ~5 credits
contact = client.web_data.get_contact_v1(company_id="DE-HRB-F1103-267645")
```

**Filter fields (all values MUST be strings):**
status, legal_form, revenue (min/max in cents), employees (min/max), balance_sheet_total, incorporated_at (YYYY-MM-DD), capital_amount, youngest_owner_age, has_sole_owner, has_representative_owner, is_family_owned, number_of_owners, industry_codes, city, zip, purpose (keywords array)

Legal form enum: ag, eg, ek, ev, ewiv, foreign, gbr, ggmbh, gmbh, kg, kgaa, llp, municipal, ohg, se, ug

## Stripe Integration Pattern

```python
import stripe

# Create 3 Checkout Sessions per job (one per package)
session = stripe.checkout.Session.create(
    mode="payment",
    line_items=[{"price": price_id, "quantity": 1}],
    customer_email=customer_email,
    metadata={"job_id": job_id, "package": "standard", "service_type": "longlist"},
    invoice_creation={"enabled": True},
    expires_at=int(time.time()) + 7 * 24 * 3600,
    success_url="https://longlist.de/danke",
    cancel_url="https://longlist.de/abgebrochen",
)
# session.url → embed in email

# Webhook: checkout.session.completed → read metadata → start pipeline
```

## File Structure to Build

```
Railway-longlist-test/
├── main.py                 # FastAPI app + 3 webhook endpoints (~150 lines)
├── config.py               # Env vars, Stripe price IDs, package definitions (~50 lines)
├── briefing_parser.py      # Claude Call #1: parse email → structured JSON (~80 lines)
├── preview_search.py       # OpenRegister Advanced Filter Search for preview (~40 lines)
├── pipeline.py             # Enrichment orchestrator: fetch + enrich N companies (~120 lines)
├── openregister_client.py  # OpenRegister wrapper: details, financials, owners, contact (~80 lines)
├── anymailfinder_client.py # Email lookup fallback (~40 lines)
├── stripe_handler.py       # Create checkout sessions + webhook handling (~60 lines)
├── excel_generator.py      # openpyxl: formatted Excel output (~100 lines)
├── email_writer.py         # Claude Call #2: delivery email (~60 lines)
├── agentmail_client.py     # Send/reply emails with attachments (~50 lines)
├── telegram_notify.py      # QA notification to Max (~30 lines)
├── requirements.txt
├── Procfile                # web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
├── .env.example
├── .gitignore
└── runtime.txt             # python-3.12
```

## Environment Variables Needed

```
ANTHROPIC_API_KEY=
OPENREGISTER_API_KEY=sk_live_GKTHqzxmpKc7vrVx9hiokH
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
AGENTMAIL_API_KEY=
AGENTMAIL_WEBHOOK_SECRET=
ANYMAILFINDER_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
APP_URL=http://localhost:8000
```

## Build Order

1. `config.py` — all env vars, price IDs, package definitions
2. `openregister_client.py` — wrapper for all OpenRegister endpoints
3. `preview_search.py` — run filter search, return count + preview names
4. `briefing_parser.py` — Claude prompt + response parsing (the big prompt is below)
5. `stripe_handler.py` — create 3 checkout sessions, webhook handler
6. `excel_generator.py` — formatted Excel with German locale
7. `pipeline.py` — orchestrate: search → enrich each company → generate Excel
8. `email_writer.py` — Claude prompt for delivery email
9. `agentmail_client.py` — send replies with attachments
10. `telegram_notify.py` — ping Max when QA ready
11. `main.py` — FastAPI with 3 endpoints, wire everything together
12. Supporting files: requirements.txt, Procfile, .env.example, .gitignore, runtime.txt

## Key Implementation Notes

- Use `AsyncOpenregister` for the pipeline (concurrent enrichment)
- All OpenRegister filter values MUST be strings (API rejects non-strings)
- `query` param in find_companies_v1 is `{"value": "search text"}`, NOT a plain string
- Revenue in cents: €1M = "100000000"
- Stripe Checkout Sessions expire after 7 days
- Stripe `invoice_creation.enabled = True` auto-sends invoice PDF to client
- Excel: German number format (Punkt = Tausender), "n/v" for missing data, light blue header row
- All email communication in formal German ("Sie"-form), sachlich tone
- Each webhook endpoint should handle errors gracefully and return 200 to avoid retries

## The Briefing Parser Prompt

This is the core intelligence of the product. It translates German M&A briefing emails into structured API calls. The full prompt with all filter field references, revenue conversion table, geography coordinate lookup, legal form mapping, and clarification rules is defined in the PRD. Key points:

- Classify: enrichment vs longlist
- Extract filters mapping to OpenRegister fields
- Convert "5 Mio Umsatz" → "500000000" (cents)
- Map "GmbH & Co. KG" → legal_form "kg"
- Map "Süddeutschland" → lat 48.5, lng 10.5, radius 250
- Map "inhabergeführt" → has_representative_owner: "true"
- Map "GF über 60" → youngest_owner_age min: "60"
- Default: status "active", details + contact if no data points specified
- Clarify only when: no industry AND no company list, or ambiguous service type

## START BUILDING

Begin with config.py and work through the build order. Make each file complete and functional. Test OpenRegister calls with the live API key. Handle missing env vars gracefully (skip Stripe/AgentMail/Telegram if keys not set, but log warnings).
