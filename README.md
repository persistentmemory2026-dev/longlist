# Longlist

Email-only Research-as-a-Service for German M&A advisors: inbound briefing at `briefing@longlist.email`, OpenRegister enrichment, Stripe checkout, Excel delivery via AgentMail. See [BUILD_PROMPT.md](BUILD_PROMPT.md) for the full product spec.

## Requirements

- Python **3.12** (see [runtime.txt](runtime.txt))
- API keys as in [.env.example](.env.example)

## Configuration

Copy `.env.example` to `.env` and set variables. Important additions:

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_PATH` | SQLite file for jobs + Stripe idempotency (default `longlist.db`). On Railway, use a **persistent volume** mount path so restarts keep job state. |
| `AGENTMAIL_WEBHOOK_SECRET` | Svix signing secret from AgentMail (`whsec_...`). When set, `/webhook/agentmail` verifies signatures (raw body required). |
| `LONGLIST_ADMIN_TOKEN` | When set, `GET /jobs`, `GET /jobs/{id}`, and `POST /webhook/manual` require `Authorization: Bearer <token>`. **Set this in production.** |
| `APP_URL` | Public base URL of this app (used for default Stripe success/cancel URLs). |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` | Optional overrides (defaults: `{APP_URL}/danke` and `{APP_URL}/abgebrochen`). |

Never commit real API keys. Rotate any key that was ever committed.

## Webhooks (production URLs)

Register these with your providers (replace host with your Railway app URL):

- **AgentMail:** `POST https://<host>/webhook/agentmail`
- **Stripe:** `POST https://<host>/webhook/stripe` (event: `checkout.session.completed`)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET /`

## Tests

```bash
pytest tests/ -q
```

## Railway

- Use the [Procfile](Procfile) command (uvicorn on `$PORT`).
- Attach a **volume** and set `DATABASE_PATH` to a path inside that volume so paid jobs survive deploys and restarts.
- Set all secrets in the Railway dashboard.

## Failure modes

- **Payment but no email:** Usually missing `thread_id` or job row (e.g. DB not persistent). Ensure `DATABASE_PATH` is on durable storage.
- **Duplicate Stripe deliveries:** Prevented by recording `checkout.session.id` in SQLite; duplicate webhooks return `{"status": "duplicate"}`.
