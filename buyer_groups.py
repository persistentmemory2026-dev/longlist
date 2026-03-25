"""Longlist — Claude: Define buyer groups for sell-side mandates."""
import json
import logging
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger("longlist.buyer_groups")

_SYSTEM = """Du bist ein Senior M&A-Berater mit Erfahrung in Käuferidentifikation.
Antworte immer NUR mit einem JSON-Array, kein weiterer Text."""

_GROUPS_PROMPT = """Definiere 3-5 Käufergruppen für dieses Sell-Side-Mandat.

Zielunternehmen:
{target_json}

Für jede Käufergruppe erstelle ein Objekt mit:
- "name": Kurzer deutscher Gruppenname (max 35 Zeichen)
- "description": 1 Satz — wer sind diese Käufer?
- "rationale": 1 Satz — warum wären sie an diesem Unternehmen interessiert?
- "query": Suchbegriff(e) für die Handelsregister-Datenbank
- "filters": Array von Filtern (ALLE Werte MÜSSEN Strings sein!)
  Verfügbare Felder:
  - {{"field": "status", "value": "active"}} (IMMER setzen)
  - {{"field": "employees", "min": "100", "max": "5000"}}
  - {{"field": "industry_codes", "value": "62"}} (WZ-Code, 2-stellig)
  - {{"field": "legal_form", "value": "gmbh"}}
  - {{"field": "is_family_owned", "value": "true"}}
  - {{"field": "has_representative_owner", "value": "true"}}
  KEINE Finanz-Filter (revenue etc.) — Daten zu lückenhaft!
- "location": {{"latitude": 51.0, "longitude": 10.0, "radius": 500}} oder null (bundesweit)

Typische Käufergruppen:
1. Strategische Käufer (gleiche Branche, typischerweise größer)
2. Horizontale Expansion (angrenzende/komplementäre Branchen)
3. Vertikale Integration (Zulieferer oder Abnehmer)
4. PE/Finanzinvestoren (mit passendem Branchenfokus — suche nach "Beteiligungsgesellschaft")
5. Branchenfremde Käufer (mit strategischem Interesse an der Technologie/Kundenbasis)

Regeln:
- Mindestens 3, maximal 5 Gruppen
- Jede Gruppe muss sich deutlich unterscheiden (verschiedene query + filters)
- Gruppen nach erwarteter Relevanz sortieren (beste zuerst)
- Mindestens eine Gruppe bundesweit (location: null)
- Filter minimal halten — je weniger Filter, desto mehr Treffer

Antworte NUR mit dem JSON-Array."""


async def define_buyer_groups(
    target_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Define 3-5 buyer groups with OpenRegister search criteria based on target analysis.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = _GROUPS_PROMPT.format(
        target_json=json.dumps(target_analysis, ensure_ascii=False, indent=2),
    )

    logger.info("Defining buyer groups for: %s", target_analysis.get("name", "?"))

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    try:
        groups = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse buyer groups: %s\nRaw: %s", e, raw_text[:500])
        return []

    if not isinstance(groups, list):
        logger.error("Buyer groups response is not a list")
        return []

    # Ensure defaults and sanitize
    for g in groups:
        g.setdefault("name", "Käufergruppe")
        g.setdefault("description", "")
        g.setdefault("rationale", "")
        g.setdefault("query", "")
        g.setdefault("filters", [{"field": "status", "value": "active"}])
        g.setdefault("location", None)

        # Ensure status filter exists
        has_status = any(f.get("field") == "status" for f in g["filters"])
        if not has_status:
            g["filters"].insert(0, {"field": "status", "value": "active"})

        # Sanitize filter values to strings
        for f in g["filters"]:
            for k, v in f.items():
                if isinstance(v, (int, float, bool)):
                    f[k] = str(v)

    logger.info("Defined %d buyer groups", len(groups))
    return groups[:5]


async def parse_buyer_selection(
    body: str,
    buyer_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Parse a customer's reply selecting how many companies per buyer group.

    Input: "60 Strategische, 40 Angrenzende, 20 PE"
    Returns: [{"group_index": 0, "count": 60}, {"group_index": 1, "count": 40}, ...]
    """
    if not ANTHROPIC_API_KEY:
        return []

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    group_names = [f'{i}: "{g["name"]}" (max {g.get("available", "?")})' for i, g in enumerate(buyer_groups)]

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system="Du parsed Kundenantworten. Antworte NUR mit JSON-Array.",
        messages=[{"role": "user", "content": f"""Der Kunde hat auf unsere Käufergruppen-Übersicht geantwortet.

Verfügbare Gruppen:
{chr(10).join(group_names)}

Kundenantwort:
{body}

Parse die Antwort und gib ein JSON-Array zurück:
[{{"group_index": 0, "count": 60}}, {{"group_index": 1, "count": 40}}, ...]

Wenn der Kunde eine Gesamtanzahl nennt (z.B. "150 gesamt"), verteile proportional
auf alle Gruppen basierend auf den verfügbaren Treffern.

Antworte NUR mit dem JSON-Array."""}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    try:
        selection = json.loads(raw_text)
        if not isinstance(selection, list):
            return []
        # Validate indices and cap counts
        for s in selection:
            idx = s.get("group_index", -1)
            if not (0 <= idx < len(buyer_groups)):
                s["group_index"] = 0
                idx = 0
            s["count"] = max(0, int(s.get("count", 0)))
            # Cap at available count per group (prevent runaway API costs)
            available = buyer_groups[idx].get("available", 500)
            s["count"] = min(s["count"], available, 500)  # Hard cap 500
        return selection
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse buyer selection: %s", e)
        return []
