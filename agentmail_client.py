"""Longlist — AgentMail client for sending/replying with attachments."""
from __future__ import annotations

import base64
import logging
from typing import Any

from agentmail import AgentMail
from agentmail.attachments.types import SendAttachment
from config import AGENTMAIL_API_KEY, AGENTMAIL_FROM

logger = logging.getLogger("longlist.agentmail")

# Inbox ID is the email address
INBOX_ID = AGENTMAIL_FROM  # "briefing-mandatscout@agentmail.to"


def _get_client() -> AgentMail | None:
    if not AGENTMAIL_API_KEY:
        logger.warning("AGENTMAIL_API_KEY not set — skipping email send")
        return None
    return AgentMail(api_key=AGENTMAIL_API_KEY)


def _build_attachments(
    attachment_path: str | None,
    attachment_name: str | None,
) -> list[SendAttachment] | None:
    """Read file and build AgentMail attachment list."""
    if not attachment_path or not attachment_name:
        return None
    try:
        with open(attachment_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")
        logger.info("Attaching file: %s", attachment_name)
        return [
            SendAttachment(
                filename=attachment_name,
                content=file_data,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ]
    except Exception as e:
        logger.error("Failed to read attachment %s: %s", attachment_path, e)
        return None


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

    Uses the SDK: client.inboxes.messages.reply(inbox_id, message_id, ...)
    We need the message_id from the thread to reply to.
    """
    client = _get_client()
    if not client:
        return {"status": "skipped", "reason": "API key not configured"}

    try:
        # Get the thread to find the last message_id to reply to
        thread = client.threads.get(thread_id=thread_id)
        if not thread.messages:
            logger.error("Thread %s has no messages to reply to", thread_id)
            return {"error": "No messages in thread"}

        last_message_id = thread.messages[-1].message_id
        logger.info("Replying to message %s in thread %s", last_message_id, thread_id)

        attachments = _build_attachments(attachment_path, attachment_name)

        result = client.inboxes.messages.reply(
            inbox_id=INBOX_ID,
            message_id=last_message_id,
            to=[to_email],
            html=body_html,
            text=body_text,
            attachments=attachments,
        )

        logger.info("Reply sent to %s in thread %s (message: %s)", to_email, thread_id, getattr(result, 'message_id', 'ok'))
        return {"status": "sent", "thread_id": thread_id}

    except Exception as e:
        logger.error("AgentMail reply failed: %s", e)
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
    Send a new email (not a reply) via AgentMail SDK.
    """
    client = _get_client()
    if not client:
        return {"status": "skipped", "reason": "API key not configured"}

    try:
        attachments = _build_attachments(attachment_path, attachment_name)

        result = client.inboxes.messages.send(
            inbox_id=INBOX_ID,
            to=[to_email],
            subject=subject,
            html=body_html,
            text=body_text,
            attachments=attachments,
        )

        logger.info("Email sent to %s: %s", to_email, subject)
        return {"status": "sent", "message_id": getattr(result, 'message_id', 'ok')}

    except Exception as e:
        logger.error("AgentMail send failed: %s", e)
        return {"error": str(e)}
