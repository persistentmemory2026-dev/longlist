"""Longlist — Telegram notification for QA alerts to Max."""
import logging

import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("longlist.telegram")

TELEGRAM_API = "https://api.telegram.org"


async def notify_qa_ready(
    job_id: str,
    customer_email: str,
    package: str,
    enriched_count: int,
    search_summary: str,
) -> bool:
    """
    Send a Telegram message to Max when a job is ready for QA review.

    Returns True if sent successfully, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured — skipping QA notification for job %s", job_id)
        return False

    message = (
        f"📋 *Longlist geliefert*\n\n"
        f"*Job:* `{job_id}`\n"
        f"*Kunde:* {customer_email}\n"
        f"*Paket:* {package.upper()}\n"
        f"*Unternehmen:* {enriched_count}\n"
        f"*Suche:* {search_summary}\n\n"
        f"Die Excel wurde automatisch an den Kunden gesendet (Antwort im "
        f"ursprünglichen E-Mail-Thread). Bitte bei Bedarf stichprobenartig prüfen."
    )

    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )

            if response.status_code == 200:
                logger.info("Telegram QA notification sent for job %s", job_id)
                return True
            else:
                logger.error("Telegram API error %d: %s", response.status_code, response.text[:200])
                return False

    except Exception as e:
        logger.error("Telegram notification failed: %s", e)
        return False


async def notify_error(
    job_id: str,
    error_msg: str,
) -> bool:
    """Send an error notification to Max via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    message = (
        f"🚨 *Longlist Fehler*\n\n"
        f"*Job:* `{job_id}`\n"
        f"*Fehler:* {error_msg[:500]}"
    )

    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
            return response.status_code == 200
    except Exception:
        return False
