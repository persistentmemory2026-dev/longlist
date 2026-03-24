"""Longlist — Preview Search via OpenRegister Advanced Filter Search."""
from __future__ import annotations

import logging
from typing import Any

from openregister import Openregister
from config import OPENREGISTER_API_KEY

logger = logging.getLogger("longlist.preview")


def run_preview_search(
    query: str,
    filters: list[dict[str, Any]] | None = None,
    location: dict[str, float] | None = None,
    per_page: int = 5,
) -> dict[str, Any]:
    """
    Run an Advanced Filter Search (10 credits per query).

    Returns:
        {
            "total": int,
            "preview_companies": [{"name": str, "company_id": str, "city": str}, ...],
            "raw": <full API response>
        }
    """
    client = Openregister(api_key=OPENREGISTER_API_KEY)

    search_kwargs: dict[str, Any] = {
        "query": {"value": query},
        "pagination": {"page": 1, "per_page": per_page},
    }
    if filters:
        search_kwargs["filters"] = filters
    if location:
        search_kwargs["location"] = location

    logger.info("Preview search: query=%s, filters=%s, location=%s", query, filters, location)

    result = client.search.find_companies_v1(**search_kwargs)

    total = result.pagination.total_results if hasattr(result, "pagination") else 0
    preview = []
    for r in result.results or []:
        entry = {
            "name": getattr(r, "name", ""),
            "company_id": getattr(r, "company_id", ""),
            "city": getattr(r, "city", ""),
        }
        # Include legal_form if available
        if hasattr(r, "legal_form"):
            entry["legal_form"] = r.legal_form
        preview.append(entry)

    logger.info("Preview search found %d total companies", total)

    return {
        "total": total,
        "preview_companies": preview,
        "raw": result.model_dump() if hasattr(result, "model_dump") else str(result),
    }
