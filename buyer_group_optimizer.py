"""Longlist — Single-pass buyer group validation: search, catch 0-result groups, batch fix."""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_client import create_message
from preview_search import run_preview_search

logger = logging.getLogger("longlist.buyer_group_optimizer")

_FIX_SYSTEM = """Du bist ein erfahrener M&A-Berater und Experte für Handelsregister-Suche.
Antworte NUR mit einem JSON-Array."""


def _sanitize_filters(filters: list[dict]) -> list[dict]:
    """Ensure all filter values are strings (OpenRegister API requirement)."""
    sanitized = []
    for f in (filters or []):
        sf = dict(f)
        for k, v in sf.items():
            if isinstance(v, (int, float, bool)):
                sf[k] = str(v)
        sanitized.append(sf)
    return sanitized


async def _batch_fix_zero_groups(
    zero_groups: list[dict[str, Any]],
    all_groups: list[dict[str, Any]],
    target_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fix all 0-result groups in a single Claude call."""
    problems = ""
    for i, g in enumerate(zero_groups):
        problems += (
            f"{i+1}. \"{g.get('name', '')}\" — "
            f"query=\"{g.get('query', '')}\", "
            f"filters={json.dumps(g.get('filters', []), ensure_ascii=False)}, "
            f"location={json.dumps(g.get('location'), ensure_ascii=False)}\n"
        )

    user_msg = f"""Diese Käufergruppen haben 0 Treffer in der Handelsregister-Suche ergeben.
Generiere für jede Gruppe verbesserte Suchparameter.

**Zielunternehmen:** {target_analysis.get("name", "")} ({target_analysis.get("industry", "")})
**Zusammenfassung:** {target_analysis.get("summary", "")}

**Gruppen mit 0 Treffern:**
{problems}

**API-Regeln (WICHTIG):**
- "query" sucht NUR nach Firmennamen — NICHT für Branchen/Keywords verwenden!
- Für Branchen-Suche den "purpose" Filter nutzen: {{"field": "purpose", "keywords": ["Keyword1", "Keyword2"]}}
- WICHTIG: Immer "keywords" verwenden, NICHT "value" (value macht exakten Match = kaum Treffer)!
- "purpose" Keywords sollten Begriffe sein die im Unternehmensgegenstand vorkommen (auf Deutsch!)
- KEINE industry_codes-Filter — WZ-Codes sind unzuverlässig, viele Firmen ohne Codes
- KEINE Finanz-Filter (revenue etc.) — Daten zu lückenhaft
- KEINE employees-Filter — nur 2% der Firmen haben diese Daten
- "status": "active" IMMER setzen
- Alle Filter-Werte müssen Strings sein
- Weniger spezifische purpose-Keywords = mehr Treffer
- Lieber breitere Keywords als zu enge

Antworte mit einem JSON-Array, ein Objekt pro Gruppe:
[
  {{
    "original_name": "Gruppenname",
    "query": "",
    "filters": [{{"field": "status", "value": "active"}}, {{"field": "purpose", "values": ["Keyword"]}}],
    "location": null,
    "change_reasoning": "Was wurde geändert und warum"
  }}
]"""

    try:
        raw = await create_message(system=_FIX_SYSTEM, user_msg=user_msg, max_tokens=2000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(l for l in raw.split("\n") if not l.startswith("```"))
        fixes = json.loads(raw)
    except (json.JSONDecodeError, RuntimeError) as e:
        logger.error("Batch fix failed: %s", e)
        return zero_groups

    if not isinstance(fixes, list):
        logger.error("Batch fix response is not a list")
        return zero_groups

    # Apply fixes to zero_groups
    for fix in fixes:
        name = fix.get("original_name", "")
        for g in zero_groups:
            if g.get("name", "") == name:
                g["query"] = fix.get("query", "")
                g["filters"] = fix.get("filters", g["filters"])
                g["location"] = fix.get("location", g.get("location"))

                # Sanitize
                for f in g["filters"]:
                    for k, v in f.items():
                        if isinstance(v, (int, float, bool)):
                            f[k] = str(v)

                # Ensure status filter
                has_status = any(f.get("field") == "status" for f in g["filters"])
                if not has_status:
                    g["filters"].insert(0, {"field": "status", "value": "active"})

                logger.info("Fixed group '%s': %s", name, fix.get("change_reasoning", ""))
                break

    return zero_groups


async def validate_buyer_groups(
    groups: list[dict[str, Any]],
    target_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Single-pass validation for buyer groups.

    1. Search each group (0 Claude calls, API only)
    2. If any have 0 results: batch fix in one Claude call
    3. Re-search fixed groups

    Returns groups with `available` and `preview_names` populated.
    """
    logger.info("Validating %d buyer groups for %s", len(groups), target_analysis.get("name", "?"))

    # Phase 1: Search all groups
    for group in groups:
        sanitized_filters = _sanitize_filters(group.get("filters", []))
        try:
            preview = run_preview_search(
                query=group.get("query", ""),
                filters=sanitized_filters,
                location=group.get("location"),
                per_page=3,
            )
            group["available"] = preview.get("total", 0)
            group["preview_names"] = [c["name"] for c in preview.get("preview_companies", [])[:3]]
        except Exception as e:
            logger.warning("Search failed for '%s': %s", group.get("name"), e)
            group["available"] = 0
            group["preview_names"] = []

    # Phase 2: Identify 0-result groups
    zero_groups = [g for g in groups if g.get("available", 0) == 0]

    if not zero_groups:
        total = sum(g.get("available", 0) for g in groups)
        logger.info("All groups have results. Total: %d", total)
        return groups

    logger.info("%d/%d groups have 0 results, attempting batch fix", len(zero_groups), len(groups))

    # Phase 3: Batch fix (1 Claude call)
    await _batch_fix_zero_groups(zero_groups, groups, target_analysis)

    # Phase 4: Re-search only the fixed groups
    for group in zero_groups:
        sanitized_filters = _sanitize_filters(group.get("filters", []))
        try:
            preview = run_preview_search(
                query=group.get("query", ""),
                filters=sanitized_filters,
                location=group.get("location"),
                per_page=3,
            )
            group["available"] = preview.get("total", 0)
            group["preview_names"] = [c["name"] for c in preview.get("preview_companies", [])[:3]]
        except Exception as e:
            logger.warning("Re-search failed for '%s': %s", group.get("name"), e)
            group["available"] = 0
            group["preview_names"] = []

    total = sum(g.get("available", 0) for g in groups)
    still_zero = sum(1 for g in groups if g.get("available", 0) == 0)
    logger.info("Validation complete: %d total available, %d still at 0", total, still_zero)

    return groups
