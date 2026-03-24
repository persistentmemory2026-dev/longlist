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
# ---------------------------------------------------------------------------
async def get_details(company_id: str) -> dict[str, Any]:
    """Fetch company details (Stammdaten, Adresse, GF, etc.)."""
    try:
        client = _get_async_client()
        result = await client.company.get_details_v1(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_details(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Contact / Web Data — ~5 credits
# ---------------------------------------------------------------------------
async def get_contact(company_id: str) -> dict[str, Any]:
    """Fetch web-sourced contact data (website, phone, email).

    The current openregister-python SDK exposes ``company.get_contact_v0`` only
    (no ``web_data`` namespace). This matches the live package API.
    """
    try:
        client = _get_async_client()
        result = await client.company.get_contact_v0(company_id=company_id)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except Exception as e:
        logger.error("get_contact(%s) failed: %s", company_id, e)
        return {"error": str(e), "company_id": company_id}


# ---------------------------------------------------------------------------
# Financials — 10 credits
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
# Mapping: endpoint name → fetch function
# ---------------------------------------------------------------------------
ENDPOINT_FETCHERS = {
    "details": get_details,
    "contact": get_contact,
    "financials": get_financials,
    "owners": get_owners,
}
