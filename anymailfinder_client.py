"""Longlist — Anymailfinder email lookup for GF email enrichment."""
import logging
from typing import Any

import httpx
from config import ANYMAILFINDER_API_KEY

logger = logging.getLogger("longlist.anymailfinder")

ANYMAILFINDER_URL = "https://api.anymailfinder.com/v5.0/search/person.json"


async def find_email(
    full_name: str,
    company_domain: str,
) -> dict[str, Any]:
    """
    Look up an email address for a person at a company domain.

    Returns: {"email": "...", "confidence": "high"/"medium"/"low", "source": "anymailfinder"}
    or {"email": None, "error": "..."} on failure.
    """
    if not ANYMAILFINDER_API_KEY:
        logger.info("ANYMAILFINDER_API_KEY not set — skipping email lookup for %s", full_name)
        return {"email": None, "error": "API key not configured"}

    if not company_domain or not full_name:
        return {"email": None, "error": "Missing name or domain"}

    # Clean domain (remove http/https/www)
    domain = company_domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.rstrip("/").split("/")[0]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                ANYMAILFINDER_URL,
                headers={"Authorization": f"Bearer {ANYMAILFINDER_API_KEY}"},
                json={
                    "full_name": full_name,
                    "domain": domain,
                },
            )

            if response.status_code == 200:
                data = response.json()
                email = data.get("email") or data.get("email_address")
                if email:
                    logger.info("Found email for %s @ %s: %s", full_name, domain, email)
                    return {
                        "email": email,
                        "confidence": data.get("confidence", "unknown"),
                        "source": "anymailfinder",
                    }
                return {"email": None, "error": "No email found"}

            elif response.status_code == 404:
                logger.info("No email found for %s @ %s", full_name, domain)
                return {"email": None, "error": "Not found"}

            else:
                logger.warning(
                    "Anymailfinder API error %d for %s: %s",
                    response.status_code, full_name, response.text[:200]
                )
                return {"email": None, "error": f"API error {response.status_code}"}

    except Exception as e:
        logger.error("Anymailfinder request failed for %s: %s", full_name, e)
        return {"email": None, "error": str(e)}
