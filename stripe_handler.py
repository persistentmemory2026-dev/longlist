"""Longlist — Stripe checkout session creation & webhook handling (dynamic per-company pricing)."""
from __future__ import annotations

import time
import logging
from typing import Any

import stripe
from config import (
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    PACKAGES,
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
    total_companies: int = 0,
) -> dict[str, str]:
    """
    Create 3 Stripe Checkout Sessions (basis/standard/premium) for a job.

    Uses dynamic price_data with quantity = total_companies so the customer
    sees "X companies × Y €/company = total" on the Stripe checkout page.

    Returns: {"basis": url, "standard": url, "premium": url}
    """
    if not STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set — returning dummy URLs")
        return {
            "basis": f"https://example.com/pay/basis/{job_id}",
            "standard": f"https://example.com/pay/standard/{job_id}",
            "premium": f"https://example.com/pay/premium/{job_id}",
        }

    # Ensure at least 1 company for the session
    qty = max(total_companies, 1)

    urls: dict[str, str] = {}

    for package_key in ("basis", "standard", "premium"):
        pkg = PACKAGES[package_key]
        unit_price = pkg["unit_price_eur_cents"]  # in EUR cents

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Longlist {pkg['label']}",
                            "description": pkg["description"],
                        },
                        "unit_amount": unit_price,
                    },
                    "quantity": qty,
                }
            ],
            customer_email=customer_email,
            metadata={
                "job_id": job_id,
                "package": package_key,
                "service_type": service_type,
                "total_companies": str(qty),
            },
            invoice_creation={"enabled": True},
            expires_at=int(time.time()) + 23 * 3600,  # 23 hours
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
        )
        urls[package_key] = session.url
        logger.info(
            "Created checkout: %s/%s — %d × %d ct = %d ct (session %s)",
            service_type, package_key, qty, unit_price, qty * unit_price, session.id,
        )

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
        "Payment completed: job_id=%s, package=%s, service=%s, customer=%s, companies=%s",
        metadata.get("job_id"),
        metadata.get("package"),
        metadata.get("service_type"),
        session.get("customer_email"),
        metadata.get("total_companies"),
    )

    return {
        "job_id": metadata.get("job_id"),
        "package": metadata.get("package"),
        "service_type": metadata.get("service_type"),
        "customer_email": session.get("customer_email"),
        "amount_total": session.get("amount_total"),
        "currency": session.get("currency"),
        "stripe_session_id": session.get("id"),
        "total_companies": metadata.get("total_companies"),
    }
