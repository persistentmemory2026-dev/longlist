# Longlist — Technical Reference

_Letzte Aktualisierung: 2026-03-25_

---

## API Endpoints (FastAPI)

| Method | Path | Auth | Beschreibung |
|--------|------|------|-------------|
| `GET` | `/` | Keine | Health Check → `{"status": "ok", "jobs_persisted": N}` |
| `GET` | `/danke` | Keine | Stripe Success-Redirect (HTML) |
| `GET` | `/abgebrochen` | Keine | Stripe Cancel-Redirect (HTML) |
| `GET` | `/doc/{document_id}` | Keine | Dokument-Proxy → Redirect auf signierte S3-URL (15 Min gültig) |
| `GET` | `/retry/{job_id}/{variant_key}` | Keine | Alternative Suche starten (aus No-Results-Email) |
| `POST` | `/webhook/agentmail` | Svix HMAC | Eingehende Emails von AgentMail |
| `POST` | `/webhook/stripe` | Stripe Signatur | Zahlungsbenachrichtigungen |
| `POST` | `/webhook/manual` | Admin Token | Manuelles Test-Briefing |
| `GET` | `/jobs` | Admin Token | Job-Übersicht |
| `GET` | `/jobs/{job_id}` | Admin Token | Job-Details |

### Admin Auth
- Header: `Authorization: Bearer {LONGLIST_ADMIN_TOKEN}`
- Wenn `LONGLIST_ADMIN_TOKEN` nicht gesetzt → alle Requests erlaubt (Dev-Modus)

---

## OpenRegister API — Verifizierte Response-Strukturen

Quelle: OpenRegister Python SDK (`oregister/openregister-python`), abgeglichen mit Nia-indexiertem Repo.

### Details Endpoint (`/v1/company/{company_id}/details`)
**Credits:** 10 | **Wrapper:** `openregister_client.get_details()`

```json
{
  "id": "DE-HRB-F1103-267645",
  "name": {                          // ⚠️ DICT, nicht String!
    "name": "Firma GmbH",
    "legal_form": "gmbh"
  },
  "names": [...],                    // Historische Namen
  "address": {
    "street": "Musterstr. 1",       // Inkl. Hausnummer
    "postal_code": "80331",          // ⚠️ "postal_code", NICHT "zip_code"
    "city": "München"
  },
  "contact": {                       // ⚠️ In Details enthalten, kein separater Endpoint
    "website_url": "https://...",    // ⚠️ "website_url", NICHT "website"
    "email": "info@firma.de",
    "phone": "+49 89 12345",
    "vat_id": "DE123456789",
    "social_media": {
      "linkedin": "...", "xing": "...", "facebook": "...",
      "instagram": "...", "twitter": "...", "youtube": "...",
      "github": "...", "tiktok": "..."
    }
  },
  "representation": [               // Geschäftsführer / Vorstand
    {
      "id": "uuid",
      "name": "Max Mustermann",
      "role": "DIRECTOR",
      "type": "natural_person",
      "start_date": "2020-01-01",
      "end_date": null,
      "natural_person": {
        "first_name": "Max",
        "last_name": "Mustermann",
        "city": "München",
        "date_of_birth": "1970-05-15"
      },
      "legal_person": null
    }
  ],
  "purpose": {                        // ⚠️ Feld heißt "purpose", NICHT "text"!
    "purpose": "Vermittlung von...",
    "start_date": "2015-02-03"
  },
  "purposes": [                      // Historisch, gleiches Format
    {"purpose": "...", "start_date": "..."}
  ],
  "indicators": [                    // ⚠️ Werte in CENTS! 2099 = 20,99 EUR
    {
      "date": "2023-12-31",
      "report_id": "...",
      "revenue": 1500000000,         // = 15.000.000,00 EUR
      "balance_sheet_total": 500000000,
      "equity": 200000000,
      "employees": 85,               // ⚠️ KEIN Cent-Wert, echte Zahl
      "net_income": 50000000,
      "liabilities": 300000000,
      "salaries": 400000000,
      "cash": 100000000,
      "real_estate": 80000000,
      "materials": 60000000,
      "pension_provisions": 20000000,
      "capital_reserves": 30000000,
      "taxes": 10000000
    }
  ],
  "documents": [                     // ⚠️ KEINE URLs! Nur Metadata
    {
      "id": "071dead2-d939-4570-...",
      "date": "2020-04-21",
      "type": "articles_of_association",  // Nur 3 Typen!
      "latest": true
    }
  ],
  "capital": {
    "amount": 26000.0,               // ⚠️ Float, NICHT String!
    "currency": "EUR",
    "start_date": "2002-09-30"
  },
  "industry_codes": {
    "wz2025": [                      // ⚠️ Verschachtelt, kommt doppelt (klein + groß)
      {"code": "66.22"},
      {"code": "66.19"}
    ],
    "WZ2025": [                      // Gleiches Array, groß geschrieben
      {"code": "66.22"},
      {"code": "66.19"}
    ]
  },
  "company_register": {
    "register_type": "HRB",
    "register_number": "267645",
    "register_court": "Frankfurt am Main"
  },
  "legal_form": "gmbh",
  "status": "active",                // "active" | "inactive" | "liquidation"
  "incorporated_at": "2015-03-20",
  "terminated_at": null
}
```

### Document Download (`/v1/document/{document_id}`)
**Wrapper:** `client.document.get_cached_v1(document_id)`

```json
{
  "id": "071dead2-...",
  "date": "2020-04-21",
  "name": "Gesellschaftsvertrag vom 21.04.2020",
  "type": "articles_of_association",
  "url": "https://cap-register-documents.s3.eu-central-1.amazonaws.com/...?X-Amz-Expires=900"
}
```
**URL gültig für 30 Minuten (`X-Amz-Expires=1800`). Proxy-Endpoint `/doc/{id}` holt jedes Mal frische URL.**

### Document Types (nur 3 existieren)
| Type | Deutsch |
|------|---------|
| `articles_of_association` | Gesellschaftsvertrag / Satzung |
| `sample_protocol` | Musterprotokoll |
| `shareholder_list` | Gesellschafterliste |

### Realtime Document Download (`/v1/document`)
**Wrapper:** `client.document.get_realtime_v1(company_id, document_category)`

Zusätzliche Kategorien (real-time abrufbar):
- `current_printout` — Aktueller Abdruck
- `chronological_printout` — Chronologischer Abdruck
- `historical_printout` — Historischer Abdruck
- `structured_information` — Strukturierte Daten

### Owners Endpoint (`/v1/company/{company_id}/owners`)
**Credits:** 10 | **Wrapper:** `openregister_client.get_owners()`

```json
{
  "owners": [
    {
      "id": "uuid-or-company-id",
      "name": "Max Mustermann",
      "percentage_share": 50.0,       // ⚠️ Prozent direkt (50.0 = 50%)
      "nominal_share": 12500.0,       // EUR
      "type": "natural_person",
      "relation_type": "SHAREHOLDER",
      "start": "2020-01-01",
      "natural_person": {
        "first_name": "Max",
        "last_name": "Mustermann",
        "city": "München",
        "date_of_birth": "1970-05-15"
      },
      "legal_person": null
    },
    {
      "name": "Holding GmbH",
      "percentage_share": 50.0,
      "type": "legal_person",
      "legal_person": {
        "name": "Holding GmbH",
        "city": "Berlin",
        "country": "DE"
      },
      "natural_person": null
    }
  ]
}
```

### UBOs Endpoint (`/v1/company/{company_id}/ubo`)
**Credits:** 25 (teuer!) | **Wrapper:** `openregister_client.get_ubos()`

```json
{
  "ubos": [
    {
      "id": "uuid",
      "name": "Max Mustermann",
      "percentage_share": 50.0,         // Exakt, wenn bekannt
      "max_percentage_share": null,      // Für KG-Gesellschafter wo Anteil unbestimmt
      "natural_person": {
        "first_name": "Max",
        "last_name": "Mustermann",
        "city": "München",
        "date_of_birth": "1970-05-15"
      },
      "legal_person": null
    }
  ]
}
```

### Holdings Endpoint (`/v1/company/{company_id}/holdings`)
**Credits:** 10 | **Wrapper:** `openregister_client.get_holdings()`

```json
{
  "holdings": [
    {
      "company_id": "DE-HRB-...",
      "name": "Tochter GmbH",
      "percentage_share": 0.75,        // ⚠️ 0.75 = 75% (Faktor, nicht Prozent!)
      "nominal_share": 18750.0,
      "relation_type": "SUBSIDIARY",
      "start": "2018-06-01",
      "end": null
    }
  ]
}
```
**⚠️ Holdings `percentage_share` ist ein Faktor (0.0-1.0), NICHT Prozent! 0.5 = 50%**

### Financials Endpoint (`/v1/company/{company_id}/financials`)
**Credits:** 10 | **Wrapper:** `openregister_client.get_financials()`

Strukturierte Jahresabschlüsse aus dem Bundesanzeiger.

### Search Endpoint (`/v1/search`)
**Credits:** 10 | **Wrapper:** `preview_search.run_preview_search()`

Filter-Felder (alle Werte MÜSSEN Strings sein):
| Feld | Werte | Beschreibung |
|------|-------|-------------|
| `status` | `"active"` | Immer setzen |
| `legal_form` | `"gmbh"`, `"ag"`, `"kg"`, etc. | Rechtsform |
| `employees` | `{"min": "50", "max": "500"}` | Mitarbeiterzahl |
| `industry_codes` | `{"value": "62"}` | WZ-Code (2-stellig) |
| `incorporated_at` | `{"max": "2000-01-01"}` | Gründung vor Datum |
| `youngest_owner_age` | `{"min": "60"}` | GF-Alter |
| `has_sole_owner` | `"true"` / `"false"` | Alleingesellschafter |
| `has_representative_owner` | `"true"` | Inhabergeführt |
| `is_family_owned` | `"true"` | Familienunternehmen |
| `city` / `zip` | `{"value": "München"}` | Ort/PLZ |
| `purpose` | `{"value": ["keyword"]}` | Gegenstand |

**⚠️ NICHT als Filter verwenden** (Daten zu lückenhaft → 0 Treffer):
- `revenue`, `balance_sheet_total`, `capital_amount`
- Stattdessen in `notes` erwähnen

---

## Tavily API — Integration

SDK: `tavily-python>=0.5.0` | Env: `TAVILY_API_KEY`

### Extract (Website scrapen)
```python
from tavily import AsyncTavilyClient
client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
result = await client.extract(
    urls="https://example.com",
    extract_depth="advanced",  # "basic" oder "advanced"
)
# result["results"][0]["raw_content"] → Markdown-Text
```

### Company Info (Firmenrecherche)
```python
info = await client.get_company_info(
    query="Unternehmensprofil Firma GmbH",
    search_depth="advanced",
    max_results=5,
)
# info → Liste von Dicts mit "content", "url", "score"
```

### Search (Web-Suche)
```python
result = await client.search(
    query="...",
    search_depth="advanced",  # "basic", "advanced", "fast", "ultra-fast"
    topic="general",          # "general", "news", "finance"
    max_results=5,
    include_answer="advanced",
    country="DE",
)
```

---

## Stripe — Checkout & Webhooks

### Checkout Session (dynamische Preise)
```python
stripe.checkout.Session.create(
    mode="payment",
    line_items=[{
        "price_data": {
            "currency": "eur",
            "product_data": {"name": "...", "description": "..."},
            "unit_amount": 150,  // Cents
        },
        "quantity": total_companies,
    }],
    customer_email="...",
    metadata={"job_id": "...", "package": "basis", "service_type": "longlist", "total_companies": "50"},
    invoice_creation={"enabled": True},  // ⚠️ Rechnung wird automatisch gesendet
    expires_at=int(time.time()) + 23 * 3600,
    success_url=STRIPE_SUCCESS_URL,
    cancel_url=STRIPE_CANCEL_URL,
)
```

### Webhook Event: `checkout.session.completed`
Metadata enthält: `job_id`, `package`, `service_type`, `total_companies`, `customer_email`

---

## AgentMail — Email-Handling

### Eingehende Email (Webhook)
Svix-verifiziert. Payload-Felder:
- `from_` / `from` → Sender-Email
- `subject` → Betreff
- `extracted_text` / `text` / `body` / `html` → Email-Body (Prioritätsreihenfolge)
- `thread_id` → Thread für Replies
- `message_id` → Message ID

### Email senden
```python
await reply_to_thread(
    thread_id="...",
    to_email="...",
    body_html="<p>...</p>",
    body_text="...",
    attachment_path="/tmp/file.xlsx",
    attachment_name="Longlist.xlsx",
)
```

---

## Datenbank-Schema (PostgreSQL)

```sql
CREATE TABLE jobs (
    job_id       TEXT PRIMARY KEY,
    status       TEXT DEFAULT 'parsing',
    sender       TEXT DEFAULT '',
    subject      TEXT DEFAULT '',
    service_type TEXT DEFAULT '',       -- "longlist", "enrichment", "sell_side"
    package      TEXT DEFAULT '',       -- "basis", "kontakt", "deep_data"
    thread_id    TEXT DEFAULT '',
    message_id   TEXT DEFAULT '',
    total_companies INTEGER DEFAULT 0,
    parsed       JSONB DEFAULT '{}',
    preview      JSONB DEFAULT '{}',
    payment_urls JSONB DEFAULT '{}',
    pipeline_result JSONB DEFAULT '{}',
    enriched_data JSONB DEFAULT '[]',
    error        TEXT DEFAULT '',
    extra        JSONB DEFAULT '{}',   -- Catch-all für sell_side buyer_groups etc.
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stripe_sessions (
    session_id TEXT PRIMARY KEY,
    job_id     TEXT REFERENCES jobs(job_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Job Status Flow

```
Longlist/Enrichment:
  parsing → preview_done → offer_sent → paid → enriching → excel_ready → delivered
                         → no_results (0 Treffer, mit Alternativen)
                         → error

Sell-Side (geplant):
  parsing → analyzing → awaiting_selection → selection_received
          → offer_sent → paid → enriching → excel_ready → delivered
          → error
```

---

## Paket-Konfiguration

| Paket | Preis/Firma | Credits | Endpoints | Extras |
|-------|------------|---------|-----------|--------|
| **Basis** | 1,50 EUR | 10 | details | KI-Scoring |
| **Kontakt** | 2,50 EUR | 20 | details, owners | + Gesellschafter |
| **Deep Data** | 4,00 EUR | 65 | details, financials, owners, ubos, holdings | + Finanzen, UBOs, Beteiligungen, GF-Email |

---

## Environment Variables

### Erforderlich
| Variable | Zweck |
|----------|-------|
| `ANTHROPIC_API_KEY` | Claude API (Briefing-Parsing, Email-Komposition) |
| `OPENREGISTER_API_KEY` | Handelsregister-Daten |

### Optional (Feature-Aktivierung)
| Variable | Zweck |
|----------|-------|
| `DATABASE_URL` | PostgreSQL Connection String (sonst SQLite) |
| `STRIPE_SECRET_KEY` | Stripe Payments |
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook-Verifizierung |
| `AGENTMAIL_API_KEY` | Email senden/empfangen |
| `AGENTMAIL_WEBHOOK_SECRET` | AgentMail Webhook-Verifizierung (Svix) |
| `TAVILY_API_KEY` | Web-Research (Sell-Side Target-Analyse) |
| `ANYMAILFINDER_API_KEY` | GF-Email-Lookup (Deep Data) |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram-Benachrichtigungen |
| `LONGLIST_ADMIN_TOKEN` | Admin-Endpoint-Schutz |
| `APP_URL` | Basis-URL für Redirects (default: `http://localhost:8000`) |

---

## Bekannte Gotchas

1. **`details.name` ist ein Dict** — `{"name": "Firma", "legal_form": "gmbh", "start_date": "..."}`
2. **Indicator-Werte wahrscheinlich in Cents** — SDK-Doku sagt Cents, aber keine Live-Testdaten verfügbar (große Firmen haben oft 0 Indicators). `employees` ist echte Zahl.
3. **Holdings `percentage_share` wahrscheinlich Faktor** — SDK sagt 0.5=50%, Live-Test steht aus (keine Holdings bei Testfirmen)
4. **Owner `percentage_share` ist Prozent** — Live bestätigt: 100.0 = 100%
5. **Dokument-URLs sind 30 Min gültig** — `X-Amz-Expires=1800`, Proxy-Endpoint `/doc/{id}` holt frische URL
6. **Nur 3 Dokument-Typen** cached: `articles_of_association`, `sample_protocol`, `shareholder_list`
7. **`purpose`-Feld heißt `.purpose`** — NICHT `.text`! Unser Code muss das korrigieren
8. **`industry_codes` doppelt** — `wz2025` UND `WZ2025` (beides Arrays mit `{code: "..."}`)
9. **`contact` ist oft None/leer** — Muss null-safe behandelt werden
10. **`capital.amount` ist Float** — NICHT String (z.B. `26000.0`)
11. **Alle Filter-Werte MÜSSEN Strings sein** — `"50"` nicht `50`
12. **Keine Finanz-Filter für Suchen** — Revenue etc. zu lückenhaft
13. **AgentMail Webhook immer 200 zurückgeben** — Sonst Svix-Retry-Loop
