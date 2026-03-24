"""Longlist — AgentMail client for sending/replying with attachments."""
from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from config import AGENTMAIL_API_KEY, AGENTMAIL_FROM

logger = logging.getLogger("longlist.agentmail")

AGENTMAIL_BASE_URL = "https://api.agentmail.to/v0"


async def reply_to_thread(
    thread_id: str,
    to_email: str,
    body_html: str,
    body_text: str | None = None,
    attachment_path: str | None = None,
    attachment_name: str | None = None,
) -> dict[str, Any]:
    """
    Reply in an existing AgentMail thread, optionally with an Excel attachment.

    Returns the API response or error dict.
    """
    if not AGENTMAIL_API_KEY:
        logger.warning("AGENTMAIL_API_KEY not set — skipping email send")
        return {"status": "skipped", "reason": "API key not configured"}

    headers = {
        "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "from": AGENTMAIL_FROM,
        "to": [to_email],
        "html": body_html,
    }

    if body_text:
        payload["text"] = body_text

    # Attach file if provided
    if attachment_path and attachment_name:
        try:
            with open(attachment_path, "rb") as f:
                file_data = base64.b64encode(f.read()).decode("utf-8")
            payload["attachments"] = [
                {
                    "filename": attachment_name,
                    "content": file_data,
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
            ]
            logger.info("Attaching file: %s", attachment_name)
        except Exception as e:
            logger.error("Failed to read attachment %s: %s", attachment_path, e)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{AGENTMAIL_BASE_URL}/threads/{thread_id}/messages"
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code in (200, 201):
                logger.info("Reply sent to %s in thread %s", to_email, thread_id)
                return response.json()
            else:
                logger.error(
                    "AgentMail reply failed (%d): %s",
                    response.status_code, response.text[:300]
                )
                return {"error": f"HTTP {response.status_code}", "detail": response.text[:300]}

    except Exception as e:
        logger.error("AgentMail request failed: %s", e)
        return {"error": str(e)}


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    attachment_path: str | None = None,
    attachment_name: str | None = None,
) -> dict[str, Any]:
    """
    Send a new email (not a reply) via AgentMail.

    Returns the API response or error dict.
    """
    if not AGENTMAIL_API_KEY:
        logger.warning("AGENTMAIL_API_KEY not set — skipping email send")
        return {"status": "skipped", "reason": "API key not configured"}

    headers = {
        "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "from": AGENTMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }

    if body_text:
        payload["text"] = body_text

    if attachment_path and attachment_name:
        try:
            with open(attachment_path, "rb") as f:
                file_data = base64.b64encode(f.read()).decode("utf-8")
            payload["attachments"] = [
                {
                    "filename": attachment_name,
                    "content": file_data,
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
            ]
        except Exception as e:
            logger.error("Failed to read attachment %s: %s", attachment_path, e)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{AGENTMAIL_BASE_URL}/emails"
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code in (200, 201):
                logger.info("Email sent to %s: %s", to_email, subject)
                return response.json()
            else:
                logger.error(
                    "AgentMail send failed (%d): %s",
                    response.status_code, response.text[:300]
                )
                return {"error": f"HTTP {response.status_code}", "detail": response.text[:300]}

    except Exception as e:
        logger.error("AgentMail send request failed: %s", e)
        return {"error": str(e)}
