"""Longlist — Preview Search via OpenRegister Advanced Filter Search."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from config import OPENREGISTER_API_KEY

logger = logging.getLogger("longlist.preview")

_SEARCH_URL = "https://api.openregister.de/v1/search/company"


def run_preview_search(
    query: str | None,
    filters: list[dict[str, Any]] | None = None,
    location: dict[str, float] | None = None,
    per_page: int = 5,
) -> dict[str, Any]:
    """
    Run an Advanced Filter Search (10 credits per query).

    Uses httpx directly instead of the SDK to avoid SequenceNotStr
    type-transform bug on Python <3.11 when using purpose keywords.

    Returns:
        {
            "total": int,
            "preview_companies": [{"name": str, "company_id": str, "city": str}, ...],
            "raw": <full API response>
        }
    """
    headers = {
        "Authorization": f"Bearer {OPENREGISTER_API_KEY}",
        "Content-Type": "application/json",
    }

    body: dict[str, Any] = {
        "pagination": {"page": 1, "per_page": per_page},
    }
    if query:
        body["query"] = {"value": query}
    if filters:
        # Strip any invalid filter fields (location is NOT a filter, it's a top-level param)
        valid_filter_fields = {
            "status", "legal_form", "register_number", "register_court", "register_type",
            "city", "active", "incorporated_at", "zip", "address", "balance_sheet_total",
            "revenue", "cash", "employees", "equity", "real_estate", "materials",
            "pension_provisions", "salaries", "taxes", "liabilities", "capital_reserves",
            "net_income", "industry_codes", "capital_amount", "capital_currency",
            "number_of_owners", "has_sole_owner", "has_representative_owner",
            "is_family_owned", "youngest_owner_age", "purpose",
        }
        cleaned = []
        for f in filters:
            if f.get("field") not in valid_filter_fields:
                continue
            # Validate filter value types: must be str, list of str, or dict with str values
            val = f.get("value") or f.get("values") or f.get("keywords")
            min_v, max_v = f.get("min"), f.get("max")
            if val is not None:
                if isinstance(val, list) and not all(isinstance(v, str) for v in val):
                    logger.warning("Stripped filter %s: list contains non-string values", f.get("field"))
                    continue
                if isinstance(val, str) and len(val) > 500:
                    logger.warning("Stripped filter %s: value too long (%d chars)", f.get("field"), len(val))
                    continue
            if min_v is not None and not isinstance(min_v, str):
                f["min"] = str(min_v)
            if max_v is not None and not isinstance(max_v, str):
                f["max"] = str(max_v)
            cleaned.append(f)
        if len(cleaned) != len(filters):
            logger.warning("Stripped %d invalid filters", len(filters) - len(cleaned))
        body["filters"] = cleaned
    if location:
        body["location"] = location

    logger.info("Preview search: query=%s, filters=%s, location=%s", query, filters, location)

    resp = httpx.post(_SEARCH_URL, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    result = resp.json()

    total = result.get("pagination", {}).get("total_results", 0)
    preview = []
    for r in result.get("results", []):
        entry = {
            "name": r.get("name", ""),
            "company_id": r.get("company_id", ""),
            "city": r.get("city", ""),
        }
        if "legal_form" in r:
            entry["legal_form"] = r["legal_form"]
        preview.append(entry)

    logger.info("Preview search found %d total companies", total)

    return {
        "total": total,
        "preview_companies": preview,
        "raw": result,
    }
