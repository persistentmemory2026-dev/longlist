"""Longlist — OpenRegister API wrapper (sync + async)."""
from __future__ import annotations

import logging
from typing import Any

from openregister import Openregister, AsyncOpenregister
from config import OPENREGISTER_API_KEY

logger = logging.getLogger("longlist.openregister")

# ---------------------------------------------------------------------------
# Sync client (used for preview search — single call)
# ---------------------------------------------------------------------------
_sync_client: Openregister | None = None


def _get_sync_client() -> Openregister:
    global _sync_client
    if _sync_client is None:
        _sync_client = Openregister(api_key=OPENREGISTER_API_KEY)
    return _sync_client


# ---------------------------------------------------------------------------
# Async client (used in enrichment pipeline — many concurrent calls)
# ---------------------------------------------------------------------------
_async_client: AsyncOpenregister | None = None


def _get_async_client() -> AsyncOpenregister:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenregister(api_key=OPENREGISTER_API_KEY)
    return _async_client


# ---------------------------------------------------------------------------
# Company Details — 10 credits
# Includes: name, address, legal_form, register, capital, contact (website,
# email, phone, social_media, vat_id), indicators, representation, purposes,
# industry_codes, documents list, status, incorporated_at, terminated_at
# NOTE: Contact endpoint is redundant — Details already includes all contact data
# ---------------------------------------------------------------------------
async def get_details(company_id: str) -> dict[str, Any]:
    """Fetch company details (Stammdaten, Adresse, GF, Kontakt, etc.)."""
    try:
        client = _get_async_client()
        result = await client.company.get_details_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_details(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Financials — 10 credits
# Detailed financial statements from Bundesanzeiger
# ---------------------------------------------------------------------------
async def get_financials(company_id: str) -> dict[str, Any]:
    """Fetch financial data (Umsatz, Bilanz, EK, Mitarbeiter)."""
    try:
        client = _get_async_client()
        result = await client.company.get_financials_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_financials(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Owners — 10 credits
# Shareholder list (name, type, share %, nominal, DOB, city)
# ---------------------------------------------------------------------------
async def get_owners(company_id: str) -> dict[str, Any]:
    """Fetch ownership / shareholder data."""
    try:
        client = _get_async_client()
        result = await client.company.get_owners_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_owners(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# UBOs (Ultimate Beneficial Owners) — 25 credits
# Computed through ownership chains
# ---------------------------------------------------------------------------
async def get_ubos(company_id: str) -> dict[str, Any]:
    """Fetch ultimate beneficial owners (wirtschaftlich Berechtigte)."""
    try:
        client = _get_async_client()
        # SDK method: company.get_ubos_v1
        result = await client.company.get_ubos_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_ubos(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Holdings — 10 credits
# Subsidiaries / investments
# ---------------------------------------------------------------------------
async def get_holdings(company_id: str) -> dict[str, Any]:
    """Fetch company holdings / subsidiaries (Beteiligungen)."""
    try:
        client = _get_async_client()
        # SDK method: company.get_holdings_v1
        result = await client.company.get_holdings_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_holdings(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Mapping: endpoint name → fetch function
# ---------------------------------------------------------------------------
ENDPOINT_FETCHERS = {
    "details": get_details,
    "financials": get_financials,
    "owners": get_owners,
    "ubos": get_ubos,
    "holdings": get_holdings,
}
