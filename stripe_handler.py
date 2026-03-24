"""Longlist — Stripe checkout session creation & webhook handling."""
from __future__ import annotations

import time
import logging
from typing import Any

import stripe
from config import (
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    STRIPE_PRICES,
    STRIPE_SUCCESS_URL,
    STRIPE_CANCEL_URL,
)

logger = logging.getLogger("longlist.stripe")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_sessions(
    job_id: str,
    service_type: str,
    customer_email: str,
) -> dict[str, str]:
    """
    Create 3 Stripe Checkout Sessions (basis/standard/premium) for a job.

    Returns: {"basis": url, "standard": url, "premium": url}
    """
    if not STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set — returning dummy URLs")
        return {
            "basis": f"https://example.com/pay/basis/{job_id}",
            "standard": f"https://example.com/pay/standard/{job_id}",
            "premium": f"https://example.com/pay/premium/{job_id}",
        }

    price_map = STRIPE_PRICES.get(service_type, STRIPE_PRICES["longlist"])
    urls: dict[str, str] = {}

    for package in ("basis", "standard", "premium"):
        price_id = price_map[package]
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=customer_email,
            metadata={
                "job_id": job_id,
                "package": package,
                "service_type": service_type,
            },
            invoice_creation={"enabled": True},
            expires_at=int(time.time()) + 23 * 3600,  # 23 hours (Stripe test mode max is 24h)
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
        )
        urls[package] = session.url
        logger.info("Created checkout session for %s/%s: %s", service_type, package, session.id)

    return urls


def verify_webhook(payload: bytes, sig_header: str) -> dict[str, Any] | None:
    """
    Verify Stripe webhook signature and extract checkout.session.completed event.

    Returns event metadata dict or None if not a relevant event.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping verification")
        return None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Stripe webhook signature verification failed: %s", e)
        return None
    except Exception as e:
        logger.error("Stripe webhook error: %s", e)
        return None

    if event["type"] != "checkout.session.completed":
        logger.info("Ignoring Stripe event type: %s", event["type"])
        return None

    session = event["data"]["object"]
    metadata = session.get("metadata", {})

    logger.info(
        "Payment completed: job_id=%s, package=%s, service=%s, customer=%s",
        metadata.get("job_id"),
        metadata.get("package"),
        metadata.get("service_type"),
        session.get("customer_email"),
    )

    return {
        "job_id": metadata.get("job_id"),
        "package": metadata.get("package"),
        "service_type": metadata.get("service_type"),
        "customer_email": session.get("customer_email"),
        "amount_total": session.get("amount_total"),
        "currency": session.get("currency"),
        "stripe_session_id": session.get("id"),
    }
