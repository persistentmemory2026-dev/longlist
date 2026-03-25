"""Longlist — FastAPI application with 3 webhook endpoints."""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import job_store
from admin_auth import require_admin
from agentmail_client import reply_to_thread
from agentmail_inbound import (
    extract_inbound_email_fields,
    verify_and_parse_agentmail_body,
)
from briefing_parser import parse_briefing, suggest_search_alternatives
from config import APP_URL
from email_html import (
    build_checkout_cta_plaintext,
    build_delivery_email_html,
    build_no_results_email_html,
    build_preview_email_html,
)
from email_writer import write_delivery_email, write_no_results_email, write_preview_email
from pipeline import run_pipeline
from preview_search import run_preview_search
from stripe_handler import create_checkout_sessions, verify_webhook
from telegram_notify import notify_error, notify_qa_ready

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("longlist.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store.init_db()
    from config import LONGLIST_ADMIN_TOKEN

    if not LONGLIST_ADMIN_TOKEN:
        logger.warning(
            "LONGLIST_ADMIN_TOKEN is not set — /jobs and /webhook/manual are open "
            "(set the token in production)"
        )
    yield


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Longlist",
    description="Email-based Research-as-a-Service for German M&A advisors",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "longlist",
        "jobs_persisted": job_store.count_jobs(),
    }


# ---------------------------------------------------------------------------
# Stripe redirect pages (branded HTML)
# ---------------------------------------------------------------------------
_BRAND_PAGE_STYLE = """
  body { margin:0; padding:0; background-color:#faf9f6; font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
         -webkit-font-smoothing:antialiased; display:flex; align-items:center; justify-content:center; min-height:100vh; }
  .card { background:#fff; border-radius:12px; border:1px solid rgba(24,24,27,0.08); padding:48px 40px;
          max-width:480px; width:90%; text-align:center; box-shadow:0 2px 4px rgba(24,24,27,0.02); }
  .logo { font-family:Georgia,'Times New Roman',serif; font-size:22px; color:#18181b; letter-spacing:-0.5px; margin-bottom:28px; }
  .logo strong { font-weight:700; } .logo span { font-weight:300; }
  .icon { font-size:48px; margin-bottom:16px; }
  h1 { font-family:Georgia,'Times New Roman',serif; font-size:24px; font-weight:700; color:#18181b; margin:0 0 12px 0; }
  p { font-size:15px; line-height:1.6; color:#71717a; margin:0 0 12px 0; }
  .footer { margin-top:32px; font-size:12px; color:#71717a; }
  a { color:#71717a; text-decoration:underline; }
"""


@app.get("/danke", response_class=HTMLResponse)
async def danke_page():
    """Stripe success redirect — thank you page."""
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vielen Dank — Longlist</title><style>{_BRAND_PAGE_STYLE}</style></head>
<body><div class="card">
  <div class="logo"><strong>Long</strong><span>list</span></div>
  <div class="icon">&#10003;</div>
  <h1>Vielen Dank!</h1>
  <p>Ihre Zahlung war erfolgreich. Wir starten jetzt mit der Recherche und liefern Ihre Longlist innerhalb von 24 Stunden per E-Mail.</p>
  <p>Sie erhalten die Rechnung separat per E-Mail von Stripe.</p>
  <div class="footer">
    <a href="https://longlist.email">longlist.email</a> &middot;
    <a href="https://longlist.email/impressum">Impressum</a> &middot;
    <a href="https://longlist.email/datenschutz">Datenschutz</a>
  </div>
</div></body></html>"""


@app.get("/abgebrochen", response_class=HTMLResponse)
async def abgebrochen_page():
    """Stripe cancel redirect — checkout cancelled page."""
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Checkout abgebrochen — Longlist</title><style>{_BRAND_PAGE_STYLE}</style></head>
<body><div class="card">
  <div class="logo"><strong>Long</strong><span>list</span></div>
  <div class="icon">&#8617;</div>
  <h1>Checkout abgebrochen</h1>
  <p>Sie haben den Checkout-Vorgang abgebrochen. Keine Sorge — es wurde nichts berechnet.</p>
  <p>Die Zahlungslinks in unserer E-Mail bleiben 23 Stunden gültig. Sie können den Vorgang jederzeit erneut starten.</p>
  <div class="footer">
    <a href="https://longlist.email">longlist.email</a> &middot;
    <a href="https://longlist.email/impressum">Impressum</a> &middot;
    <a href="https://longlist.email/datenschutz">Datenschutz</a>
  </div>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Document proxy — serves fresh signed URLs for OpenRegister documents
# ---------------------------------------------------------------------------
@app.get("/doc/{document_id}")
async def proxy_document(document_id: str):
    """Fetch a fresh signed S3 URL from OpenRegister and redirect to it."""
    from fastapi.responses import RedirectResponse
    from openregister import Openregister
    from config import OPENREGISTER_API_KEY

    if not OPENREGISTER_API_KEY:
        return JSONResponse({"error": "OpenRegister not configured"}, status_code=503)
    try:
        client = Openregister(api_key=OPENREGISTER_API_KEY)
        doc = client.document.get_cached_v1(document_id=document_id)
        if not doc.url:
            return JSONResponse({"error": "Document URL not available"}, status_code=404)
        return RedirectResponse(url=doc.url)
    except Exception as e:
        logger.error("Document proxy failed for %s: %s", document_id, e)
        return JSONResponse({"error": "Document not found"}, status_code=404)


# ---------------------------------------------------------------------------
# Retry search — customer clicks alternative search button from no-results email
# ---------------------------------------------------------------------------
@app.get("/retry/{job_id}/{variant_key}")
async def retry_search(job_id: str, variant_key: str, background_tasks: BackgroundTasks):
    """
    Customer clicked an alternative search button.
    Re-runs the offer flow with adjusted parameters in the same thread.
    """
    job = job_store.get_job(job_id)
    if not job:
        return HTMLResponse("Job nicht gefunden.", status_code=404)

    extra = job.get("extra", {})
    alternatives = extra.get("alternatives", [])
    try:
        idx = int(variant_key.replace("v", ""))
        alt = alternatives[idx]
    except (ValueError, IndexError):
        return HTMLResponse("Ungültige Suchoption.", status_code=400)

    # Store adjusted params and kick off the offer flow in background
    sender = job.get("sender", "")
    thread_id = job.get("thread_id", "")
    original_parsed = extra.get("original_parsed", {})

    # Build a new parsed briefing from the alternative
    new_parsed = {
        **original_parsed,
        "query": alt.get("query", original_parsed.get("query", "")),
        "filters": alt.get("filters", original_parsed.get("filters", [])),
        "location": alt.get("location", original_parsed.get("location")),
        "notes": f"{original_parsed.get('notes', '')} [Angepasste Suche: {alt.get('title', '')}]",
    }

    job_store.merge_job(job_id, {
        "status": "retry_search",
        "parsed": new_parsed,
    })

    background_tasks.add_task(
        process_retry_search, job_id, sender, thread_id, new_parsed,
    )

    # Redirect to confirmation page
    return HTMLResponse(
        f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Neue Suche gestartet — Longlist</title><style>{_BRAND_PAGE_STYLE}</style></head>
<body><div class="card">
  <div class="logo"><strong>Long</strong><span>list</span></div>
  <div class="icon">&#128269;</div>
  <h1>Neue Suche gestartet</h1>
  <p>Wir führen die angepasste Recherche durch und senden Ihnen die Ergebnisse in Kürze per E-Mail.</p>
  <div class="footer">
    <a href="https://longlist.email">longlist.email</a> &middot;
    <a href="https://longlist.email/impressum">Impressum</a> &middot;
    <a href="https://longlist.email/datenschutz">Datenschutz</a>
  </div>
</div></body></html>""",
        status_code=200,
    )


async def process_retry_search(
    job_id: str,
    sender: str,
    thread_id: str,
    parsed: dict[str, Any],
):
    """Background task: re-run preview search with adjusted parameters and send offer."""
    try:
        preview = run_preview_search(
            query=parsed.get("query", ""),
            filters=parsed.get("filters"),
            location=parsed.get("location"),
            per_page=5,
        )
        total_companies = preview["total"]
        preview_names = [c["name"] for c in preview["preview_companies"]]
        job_store.merge_job(job_id, {
            "preview": preview,
            "total_companies": total_companies,
            "status": "preview_done",
        })

        if total_companies == 0:
            job_store.merge_job(job_id, {"status": "no_results"})
            logger.warning("Retry search for job %s also returned 0 results", job_id)
            return

        payment_urls = create_checkout_sessions(
            job_id=job_id,
            service_type="longlist",
            customer_email=sender,
            total_companies=total_companies,
        )
        job_store.merge_job(job_id, {"payment_urls": payment_urls})

        email_body = await write_preview_email(
            total_companies=total_companies,
            preview_names=preview_names,
            search_summary=parsed.get("notes", ""),
            payment_urls=payment_urls,
            service_type="longlist",
        )

        email_plain = email_body + build_checkout_cta_plaintext(payment_urls, total_companies)
        email_html = build_preview_email_html(email_body, payment_urls, total_companies)

        if thread_id:
            await reply_to_thread(
                thread_id=thread_id,
                to_email=sender,
                body_html=email_html,
                body_text=email_plain,
            )

        job_store.merge_job(job_id, {"status": "offer_sent"})
        logger.info(
            "Job %s: Retry offer sent to %s (%d companies)",
            job_id, sender, total_companies,
        )

    except Exception as e:
        logger.exception("Error in retry search for job %s: %s", job_id, e)
        job_store.merge_job(job_id, {"status": "error", "error": str(e)})
        await notify_error(job_id, str(e))


# ---------------------------------------------------------------------------
# 1. AgentMail Webhook — incoming email
# ---------------------------------------------------------------------------
@app.post("/webhook/agentmail")
async def agentmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives incoming emails from AgentMail.
    Flow: Parse briefing → Preview search → Reply with payment links.
    """
    raw_body = await request.body()
    payload, err = verify_and_parse_agentmail_body(raw_body, request.headers)
    if err:
        logger.error("AgentMail webhook rejected: %s", err)
        # Return 200 even on error — Svix retries on non-2xx, causing infinite loops
        return JSONResponse({"status": "error", "detail": err}, status_code=200)

    if payload.get("_longlist_ignore_event"):
        return {"status": "ignored", "reason": payload.get("event_type")}

    sender, subject, body, thread_id, message_id = extract_inbound_email_fields(payload)

    logger.info("Incoming email from %s: %s (message_id=%s)", sender, subject, message_id)

    job_id = str(uuid.uuid4())[:8]
    job_store.put_job(
        job_id,
        {
            "status": "parsing",
            "sender": sender,
            "subject": subject,
            "thread_id": thread_id,
            "message_id": message_id,
        },
    )

    background_tasks.add_task(process_incoming_email, job_id, sender, subject, body, thread_id)

    return {"status": "accepted", "job_id": job_id}


async def process_incoming_email(
    job_id: str,
    sender: str,
    subject: str,
    body: str,
    thread_id: str,
):
    """Background task: parse briefing, run preview, send offer email."""
    try:
        parsed = await parse_briefing(sender=sender, subject=subject, body=body)
        job_store.merge_job(
            job_id,
            {"parsed": parsed, "status": "parsed", "service_type": parsed.get("service_type")},
        )

        if parsed.get("needs_clarification"):
            question = parsed.get(
                "clarification_question",
                "Können Sie Ihre Anfrage bitte präzisieren?",
            )
            if thread_id:
                await reply_to_thread(
                    thread_id=thread_id,
                    to_email=sender,
                    body_html=f"<p>{question}</p><p>Mit freundlichen Grüßen<br>Max Zwisler<br>Longlist Research</p>",
                    body_text=question,
                )
            job_store.merge_job(job_id, {"status": "awaiting_clarification"})
            return

        service_type = parsed["service_type"]

        total_companies = 0
        preview_names: list[str] = []

        if service_type == "longlist":
            preview = run_preview_search(
                query=parsed.get("query", ""),
                filters=parsed.get("filters"),
                location=parsed.get("location"),
                per_page=5,
            )
            total_companies = preview["total"]
            preview_names = [c["name"] for c in preview["preview_companies"]]
            job_store.merge_job(job_id, {"preview": preview})

        elif service_type == "enrichment":
            company_list = parsed.get("company_list", [])
            total_companies = len(company_list) if company_list else 0
            preview_names = (company_list or [])[:5]

        job_store.merge_job(
            job_id,
            {"total_companies": total_companies, "status": "preview_done"},
        )

        # No results → test alternatives, send follow-up with retry buttons
        if total_companies == 0 and service_type == "longlist":
            # 1. Generate and test alternative search parameters
            alternatives = await suggest_search_alternatives(
                query=parsed.get("query", ""),
                filters=parsed.get("filters", []),
                location=parsed.get("location"),
                notes=parsed.get("notes", ""),
            )

            tested: list[dict[str, Any]] = []
            for alt in alternatives[:3]:
                try:
                    # Ensure all filter values are strings (OpenRegister API requirement)
                    sanitized_filters = []
                    for f in (alt.get("filters") or []):
                        sf = dict(f)
                        for k, v in sf.items():
                            if isinstance(v, (int, float, bool)):
                                sf[k] = str(v)
                        sanitized_filters.append(sf)

                    result = run_preview_search(
                        query=alt.get("query", ""),
                        filters=sanitized_filters,
                        location=alt.get("location"),
                        per_page=3,
                    )
                    if result["total"] > 0:
                        tested.append({
                            **alt,
                            "total": result["total"],
                            "preview": [c["name"] for c in result["preview_companies"][:3]],
                        })
                except Exception as e:
                    logger.warning("Alternative search failed: %s", e)

            # 2. Build retry URLs
            retry_urls: dict[str, str] = {}
            for i in range(len(tested)):
                retry_urls[f"v{i}"] = f"{APP_URL}/retry/{job_id}/v{i}"

            # 3. Persist alternatives in job
            job_store.merge_job(job_id, {
                "status": "no_results",
                "extra": {"alternatives": tested, "original_parsed": parsed},
            })

            # 4. Send email with retry buttons
            no_results_body = await write_no_results_email(
                search_summary=parsed.get("notes", subject),
                query=parsed.get("query", ""),
                filters=parsed.get("filters", []),
                location=parsed.get("location"),
            )
            no_results_html = build_no_results_email_html(
                body_plain=no_results_body,
                alternatives=tested,
                retry_urls=retry_urls,
            )

            if thread_id:
                await reply_to_thread(
                    thread_id=thread_id,
                    to_email=sender,
                    body_html=no_results_html,
                    body_text=no_results_body,
                )

            logger.info(
                "Job %s: No results, %d alternatives found, sent to %s",
                job_id, len(tested), sender,
            )
            return

        payment_urls = create_checkout_sessions(
            job_id=job_id,
            service_type=service_type,
            customer_email=sender,
            total_companies=total_companies,
        )
        job_store.merge_job(job_id, {"payment_urls": payment_urls})

        email_body = await write_preview_email(
            total_companies=total_companies,
            preview_names=preview_names,
            search_summary=parsed.get("notes", subject),
            payment_urls=payment_urls,
            service_type=service_type,
        )

        email_plain = email_body + build_checkout_cta_plaintext(payment_urls, total_companies)
        email_html = build_preview_email_html(email_body, payment_urls, total_companies)

        if thread_id:
            reply_result = await reply_to_thread(
                thread_id=thread_id,
                to_email=sender,
                body_html=email_html,
                body_text=email_plain,
            )
            if reply_result.get("error"):
                logger.error("Job %s: Reply failed: %s", job_id, reply_result["error"])
                job_store.merge_job(job_id, {"status": "error", "error": f"Reply failed: {reply_result['error']}"})
                await notify_error(job_id, f"Reply failed: {reply_result['error']}")
                return

        job_store.merge_job(job_id, {"status": "offer_sent"})
        logger.info(
            "Job %s: Offer sent to %s (%d companies found)",
            job_id,
            sender,
            total_companies,
        )

    except Exception as e:
        logger.exception("Error processing email for job %s: %s", job_id, e)
        job_store.merge_job(job_id, {"status": "error", "error": str(e)})
        await notify_error(job_id, str(e))


# ---------------------------------------------------------------------------
# 2. Stripe Webhook — payment completed
# ---------------------------------------------------------------------------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Stripe checkout.session.completed events.
    Triggers the enrichment pipeline.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")
    except Exception:
        return JSONResponse({"status": "error"}, status_code=200)

    event_data = verify_webhook(payload, sig_header)

    if event_data is None:
        return {"status": "ignored"}

    job_id = event_data.get("job_id") or ""
    package = event_data.get("package", "basis")
    service_type = event_data.get("service_type", "longlist")
    session_id = event_data.get("stripe_session_id") or ""
    if not session_id:
        logger.error("Stripe checkout.session.completed missing session id")
        return {"status": "ignored"}

    if not job_store.try_claim_stripe_session(session_id, job_id):
        return {"status": "duplicate"}

    logger.info("Payment received for job %s: package=%s", job_id, package)

    if job_store.get_job(job_id):
        job_store.merge_job(job_id, {"status": "paid", "package": package})
    else:
        job_store.put_job(
            job_id,
            {
                "status": "paid",
                "package": package,
                "service_type": service_type,
                "sender": event_data.get("customer_email", ""),
                "parsed": {},
                "thread_id": "",
            },
        )

    background_tasks.add_task(process_payment, job_id, package, service_type, event_data)

    return {"status": "accepted", "job_id": job_id}


async def process_payment(
    job_id: str,
    package: str,
    service_type: str,
    event_data: dict[str, Any],
):
    """Background task: run enrichment pipeline, notify QA, send delivery email."""
    try:
        job = job_store.get_job(job_id) or {}
        parsed_briefing = job.get("parsed", {})
        customer_email = event_data.get("customer_email") or job.get("sender", "")
        thread_id = job.get("thread_id", "")
        search_summary = parsed_briefing.get("notes", "")

        job_store.merge_job(job_id, {"status": "enriching"})

        result = await run_pipeline(
            job_id=job_id,
            service_type=service_type,
            package=package,
            parsed_briefing=parsed_briefing,
        )

        job_store.merge_job(job_id, {"pipeline_result": result, "status": "enrichment_done"})

        excel_path = result.get("excel_path")
        enriched_count = result.get("enriched_count", 0)

        if not excel_path:
            logger.error("No Excel generated for job %s", job_id)
            await notify_error(job_id, "Pipeline produced no results")
            return

        await notify_qa_ready(
            job_id=job_id,
            customer_email=customer_email,
            package=package,
            enriched_count=enriched_count,
            search_summary=search_summary,
        )

        delivery_body = await write_delivery_email(
            enriched_count=enriched_count,
            package=package,
            search_summary=search_summary,
        )

        delivery_html = build_delivery_email_html(delivery_body)
        excel_filename = os.path.basename(excel_path)

        if thread_id:
            await reply_to_thread(
                thread_id=thread_id,
                to_email=customer_email,
                body_html=delivery_html,
                body_text=delivery_body,
                attachment_path=excel_path,
                attachment_name=excel_filename,
            )

        job_store.merge_job(job_id, {"status": "delivered"})
        logger.info(
            "Job %s delivered: %d companies, package %s",
            job_id,
            enriched_count,
            package,
        )

    except Exception as e:
        logger.exception("Error in pipeline for job %s: %s", job_id, e)
        job_store.merge_job(job_id, {"status": "error", "error": str(e)})
        await notify_error(job_id, str(e))


# ---------------------------------------------------------------------------
# 3. Manual trigger / QA endpoint
# ---------------------------------------------------------------------------
@app.post("/webhook/manual")
async def manual_trigger(
    request: Request,
    background_tasks: BackgroundTasks,
    _admin: Annotated[None, Depends(require_admin)],
):
    """
    Manual trigger for testing: accepts a briefing directly.
    Body: {"sender": "...", "subject": "...", "body": "...", "thread_id": "..."}
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "detail": "Invalid JSON"}, status_code=400)

    sender = payload.get("sender", "test@example.com")
    subject = payload.get("subject", "Test Briefing")
    body = payload.get("body", "")
    thread_id = payload.get("thread_id", "")

    job_id = str(uuid.uuid4())[:8]
    job_store.put_job(
        job_id,
        {
            "status": "parsing",
            "sender": sender,
            "subject": subject,
            "thread_id": thread_id,
        },
    )

    background_tasks.add_task(process_incoming_email, job_id, sender, subject, body, thread_id)

    return {"status": "accepted", "job_id": job_id}


@app.get("/jobs")
async def list_jobs(_admin: Annotated[None, Depends(require_admin)]):
    """List all jobs and their current status."""
    return job_store.list_jobs_summary()


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, _admin: Annotated[None, Depends(require_admin)]):
    """Get full details for a specific job."""
    job = job_store.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job
