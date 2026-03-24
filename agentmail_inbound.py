"""Verify AgentMail (Svix) webhooks and normalize payload for the inbound email handler."""
from __future__ import annotations

import json
import logging
from typing import Any

from svix.webhooks import Webhook, WebhookVerificationError

logger = logging.getLogger("longlist.agentmail_inbound")


def verify_and_parse_agentmail_body(
    raw_body: bytes,
    headers: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Verify Svix signature when AGENTMAIL_WEBHOOK_SECRET is set; parse JSON body.

    Returns (payload_dict, None) on success, or (None, error_detail) on failure.
    """
    from config import AGENTMAIL_WEBHOOK_SECRET

    if AGENTMAIL_WEBHOOK_SECRET:
        try:
            wh = Webhook(AGENTMAIL_WEBHOOK_SECRET)
            msg = wh.verify(raw_body, _headers_for_svix(headers))
        except WebhookVerificationError as e:
            logger.warning("AgentMail webhook verification failed: %s", e)
            return None, "Invalid webhook signature"
        if not isinstance(msg, dict):
            msg = dict(msg)
        payload = _normalize_svix_payload(msg)
        return payload, None

    logger.warning(
        "AGENTMAIL_WEBHOOK_SECRET not set — accepting webhook without verification (dev only)"
    )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"Invalid JSON: {e}"
    return payload, None


def _headers_for_svix(headers: Any) -> dict[str, str]:
    """Build a plain dict of headers for Svix (case-insensitive keys)."""
    if hasattr(headers, "items"):
        return {k: v for k, v in headers.items()}
    return dict(headers)


def _normalize_svix_payload(msg: dict[str, Any]) -> dict[str, Any]:
    """
    AgentMail sends event_type + data; flatten to the shape expected by main.extract_inbound_fields.
    """
    event_type = msg.get("event_type") or msg.get("type")
    if event_type and event_type != "message.received":
        logger.info("Ignoring AgentMail event type: %s", event_type)
        return {"_longlist_ignore_event": True, "event_type": event_type}

    data = msg.get("data")
    if isinstance(data, dict):
        if "message" in data:
            return data
        return {"message": data, "data": data}
    return msg


def extract_inbound_email_fields(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    """Parse AgentMail-style JSON into sender, subject, body, thread_id."""
    message = payload.get("message") or payload.get("data", {}).get("message") or payload
    if not isinstance(message, dict):
        message = {}
    from_ = message.get("from", {})
    sender = (
        from_.get("email")
        if isinstance(from_, dict)
        else (from_ if isinstance(from_, str) else "unknown@example.com")
    )
    subject = message.get("subject", "") or ""
    body = (
        message.get("text")
        or message.get("body")
        or message.get("html", "")
        or ""
    )
    thread_id = message.get("thread_id") or message.get("threadId") or ""
    return sender, subject, body, thread_id
