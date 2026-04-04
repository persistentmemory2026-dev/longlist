"""Longlist — Claude: Define buyer groups for sell-side mandates."""
import json
import logging
from typing import Any

from config import ANTHROPIC_API_KEY
from ai_client import create_message

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
- "query": Firmenname ODER leer ("") — WICHTIG: Sucht NUR nach Firmennamen, NICHT nach Branchen/Keywords!
  Nur verwenden wenn nach einem konkreten Firmennamen gesucht wird. Sonst leer lassen ("").
- "filters": Array von Filtern (ALLE Werte MÜSSEN Strings sein!)
  Verfügbare Felder:
  - {{"field": "status", "value": "active"}} (IMMER setzen)
  - {{"field": "purpose", "keywords": ["Keyword1", "Keyword2"]}} — Keyword-Suche im Unternehmensgegenstand! WICHTIGSTES Suchfeld!
    WICHTIG: Immer "keywords" (nicht "value") verwenden — "value" macht exakten Match und liefert kaum Treffer!
  - {{"field": "legal_form", "value": "gmbh"}}
  - {{"field": "is_family_owned", "value": "true"}}
  - {{"field": "has_representative_owner", "value": "true"}}
  KEINE Finanz-Filter (revenue etc.) — Daten zu lückenhaft!
  KEINE employees-Filter — nur 2% der Firmen haben Mitarbeiterdaten!
  KEINE industry_codes-Filter — WZ-Codes sind unzuverlässig zugeordnet, viele Firmen ohne Codes!
  Bevorzuge "purpose" mit "keywords" für präzise deutsche Keywords zum Unternehmensgegenstand.
- "location": {{"latitude": 51.0, "longitude": 10.0, "radius": 500}} oder null (bundesweit)

WICHTIG: Wir suchen NUR strategische Käufer (operative Unternehmen).
KEINE Finanzinvestoren, KEINE PE-Fonds, KEINE Family Offices, KEINE Beteiligungsgesellschaften.
Unsere Datenbank enthält nur Handelsregister-Firmen — keine Investoren.

Typische Kategorien strategischer Käufer:
1. Direkte Wettbewerber (gleiche Branche, gleiche/ähnliche Produkte, typischerweise größer)
2. Horizontale Expandierer (angrenzende/komplementäre Branchen die ins Zielgebiet expandieren wollen)
3. Vertikale Integrierer (Zulieferer oder Abnehmer in der Wertschöpfungskette des Zielunternehmens)
4. Branchenfremde Strategen (Unternehmen die Technologie, Kundenbasis oder Know-how des Ziels für Diversifikation nutzen könnten)

Denke wie ein M&A-Berater:
- Wer profitiert am meisten von den Synergien mit dem Zielunternehmen?
- Wer hat ein strategisches Motiv? (Marktanteil, Technologie, Kunden, Geografie)
- Wer ist groß genug für eine Akquisition dieser Größenordnung?

Regeln:
- Mindestens 3, maximal 5 Gruppen
- Jede Gruppe muss sich deutlich unterscheiden (verschiedene purpose-Keywords + filters)
- Gruppen nach erwarteter Relevanz sortieren (beste zuerst)
- Mindestens eine Gruppe bundesweit (location: null)
- Filter minimal halten — je weniger Filter, desto mehr Treffer
- NUR operative Unternehmen, KEINE Investoren/Fonds
- "query" fast immer leer ("") — Branchen-Suche geht über "purpose" Filter!

Antworte NUR mit dem JSON-Array."""


async def define_buyer_groups(
    target_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Define 3-5 buyer groups with OpenRegister search criteria based on target analysis.
    """
    user_msg = _GROUPS_PROMPT.format(
        target_json=json.dumps(target_analysis, ensure_ascii=False, indent=2),
    )

    logger.info("Defining buyer groups for: %s", target_analysis.get("name", "?"))

    raw_text = await create_message(
        system=_SYSTEM,
        user_msg=user_msg,
        max_tokens=3000,
    )
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
    group_names = [f'{i}: "{g["name"]}" (max {g.get("available", "?")})' for i, g in enumerate(buyer_groups)]

    user_msg = f"""Der Kunde hat auf unsere Käufergruppen-Übersicht geantwortet.

Verfügbare Gruppen:
{chr(10).join(group_names)}

Kundenantwort:
{body}

Parse die Antwort und gib ein JSON-Array zurück:
[{{"group_index": 0, "count": 60}}, {{"group_index": 1, "count": 40}}, ...]

Wenn der Kunde eine Gesamtanzahl nennt (z.B. "150 gesamt"), verteile proportional
auf alle Gruppen basierend auf den verfügbaren Treffern.

Antworte NUR mit dem JSON-Array."""

    try:
        raw_text = await create_message(
            system="Du parsed Kundenantworten. Antworte NUR mit JSON-Array.",
            user_msg=user_msg,
            max_tokens=500,
        )
    except RuntimeError:
        return []

    raw_text = raw_text.strip()
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
