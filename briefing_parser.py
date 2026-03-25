"""Longlist — Claude Call #1: Parse M&A briefing email into structured JSON."""
import json
import logging
from typing import Any

import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger("longlist.parser")

SYSTEM_PROMPT = """Du bist der Briefing-Parser von Longlist, einem Research-as-a-Service für deutsche M&A-Berater.

Deine Aufgabe: Analysiere die eingehende E-Mail und extrahiere strukturierte Suchparameter für die OpenRegister API.

## Entscheidung 1: Service-Typ
- "enrichment" (Service 1): Kunde liefert eine LISTE konkreter Firmennamen → wir reichern diese an
- "longlist" (Service 2): Kunde beschreibt KRITERIEN → wir suchen passende Unternehmen

## Entscheidung 2: Suchparameter extrahieren

Gib ein JSON-Objekt zurück mit genau dieser Struktur:

```json
{
  "service_type": "longlist" | "enrichment",
  "query": "Suchbegriff für Branche/Tätigkeit",
  "filters": [
    {"field": "status", "value": "active"},
    {"field": "legal_form", "value": "gmbh"},
    ...
  ],
  "location": {"latitude": 48.5, "longitude": 10.5, "radius": 250.0} | null,
  "company_list": ["Firma A GmbH", "Firma B AG"] | null,
  "notes": "Kurze Zusammenfassung was der Kunde sucht",
  "needs_clarification": false,
  "clarification_question": null
}
```

## Filter-Felder (alle Werte MÜSSEN Strings sein!)

- status: "active" (Standard, immer setzen)
- legal_form: ag, eg, ek, ev, ewiv, foreign, gbr, ggmbh, gmbh, kg, kgaa, llp, municipal, ohg, se, ug
- employees: {"field": "employees", "min": "50", "max": "500"}
- incorporated_at: {"field": "incorporated_at", "max": "2000-01-01"} für "etabliert"
- youngest_owner_age: {"field": "youngest_owner_age", "min": "60"} für "GF über 60"
- has_sole_owner: "true"/"false"
- has_representative_owner: "true" für "inhabergeführt"
- is_family_owned: "true" für "Familienunternehmen"
- number_of_owners: min/max
- industry_codes: {"field": "industry_codes", "value": "28"} (WZ-Code)
- city, zip: {"field": "city", "value": "München"}
- purpose: {"field": "purpose", "value": ["keywords"]}

WICHTIG — NICHT als Filter verwenden (Daten zu lückenhaft, führt zu 0 Ergebnissen):
- revenue (Umsatz) → stattdessen in "notes" erwähnen
- balance_sheet_total → stattdessen in "notes" erwähnen
- capital_amount → stattdessen in "notes" erwähnen
Wenn der Kunde Umsatz-/Finanzkriterien nennt, schreibe sie in die "notes" aber NICHT in die filters.

## Rechtsform-Mapping
- "GmbH" → "gmbh"
- "GmbH & Co. KG" / "KG" → "kg"
- "AG" → "ag"
- "UG" → "ug"
- "gGmbH" → "ggmbh"
- "e.V." → "ev"
- "SE" → "se"
- "OHG" → "ohg"
- "eK" → "ek"

## Geografie-Mapping (Koordinaten + Radius in km)
- "Süddeutschland" → lat 48.5, lng 10.5, radius 250
- "Norddeutschland" → lat 53.5, lng 10.0, radius 250
- "Bayern" → lat 48.8, lng 11.5, radius 150
- "Baden-Württemberg" / "BW" → lat 48.5, lng 9.0, radius 120
- "NRW" / "Nordrhein-Westfalen" → lat 51.4, lng 7.5, radius 130
- "Hessen" → lat 50.6, lng 9.0, radius 100
- "Sachsen" → lat 51.0, lng 13.0, radius 100
- "Berlin" → lat 52.52, lng 13.41, radius 50
- "München" → lat 48.14, lng 11.58, radius 50
- "Hamburg" → lat 53.55, lng 10.0, radius 50
- "Frankfurt" → lat 50.11, lng 8.68, radius 50
- "Stuttgart" → lat 48.78, lng 9.18, radius 50
- "Köln" / "Düsseldorf" / "Rheinland" → lat 51.0, lng 6.95, radius 80
- "DACH" / "Deutschland" → keine location (bundesweit)
- "Ruhrgebiet" → lat 51.45, lng 7.2, radius 60
- "Ostdeutschland" → lat 51.5, lng 12.5, radius 200

## Keyword-Mapping
- "inhabergeführt" / "eigentümergeführt" → has_representative_owner: "true"
- "GF über 60" / "Nachfolge" → youngest_owner_age min: "60"
- "Familienunternehmen" → is_family_owned: "true"
- "Alleingesellschafter" → has_sole_owner: "true"

## Wann Rückfrage stellen (needs_clarification: true)
NUR wenn:
1. Keine Branche UND keine Firmenliste erkennbar
2. Service-Typ komplett unklar (weder Liste noch Kriterien)

NICHT rückfragen bei:
- Fehlender Region (→ bundesweit suchen)
- Fehlender Rechtsform (→ weglassen)
- Fehlender Umsatz (→ weglassen)

## Default-Verhalten
- Immer status: "active" setzen
- Wenn keine spezifischen Datenpunkte genannt → alle Basis-Daten liefern
"""

USER_PROMPT_TEMPLATE = """Analysiere diese E-Mail und extrahiere die Suchparameter:

Von: {sender}
Betreff: {subject}

{body}

Antworte NUR mit dem JSON-Objekt, kein weiterer Text."""


async def parse_briefing(
    sender: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """
    Parse an incoming briefing email into structured search parameters.

    Returns a dict with: service_type, query, filters, location,
    company_list, notes, needs_clarification, clarification_question
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = USER_PROMPT_TEMPLATE.format(
        sender=sender,
        subject=subject,
        body=body,
    )

    logger.info("Parsing briefing from %s: %s", sender, subject)

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s\nRaw: %s", e, raw_text)
        raise ValueError(f"Claude returned invalid JSON: {e}") from e

    # Ensure defaults
    parsed.setdefault("service_type", "longlist")
    parsed.setdefault("query", "")
    parsed.setdefault("filters", [])
    parsed.setdefault("location", None)
    parsed.setdefault("company_list", None)
    parsed.setdefault("notes", "")
    parsed.setdefault("needs_clarification", False)
    parsed.setdefault("clarification_question", None)

    # Always ensure status: active filter is present
    has_status = any(f.get("field") == "status" for f in parsed["filters"])
    if not has_status:
        parsed["filters"].insert(0, {"field": "status", "value": "active"})

    logger.info("Parsed briefing: service=%s, query=%s, %d filters",
                parsed["service_type"], parsed["query"], len(parsed["filters"]))

    return parsed


_ALTERNATIVES_PROMPT = """Die folgende Longlist-Suche hat 0 Treffer ergeben. Schlage 2-3 alternative Suchparameter-Sets vor, die wahrscheinlich Ergebnisse liefern.

Originale Suchparameter:
- query: {query}
- filters: {filters}
- location: {location}
- Kundenwunsch: {notes}

Strategien (wähle die 2-3 passendsten):
1. Region erweitern (größerer Radius oder ganz weglassen)
2. Branchencode ändern oder ergänzen (verwandte WZ-Codes)
3. Suchbegriff variieren (Synonyme, verwandte Begriffe)
4. Restriktive Filter lockern (employees, legal_form etc. weglassen)
5. Filter-Kombination vereinfachen (weniger Filter = mehr Treffer)

WICHTIG:
- Jede Alternative MUSS sich deutlich von der Original-Suche unterscheiden
- Jede Alternative braucht einen kurzen deutschen "title" (max 40 Zeichen) für den Button-Text
- Verwende dasselbe JSON-Schema wie die Original-Suche
- Immer status: "active" als Filter beibehalten
- KEINE Finanz-Filter (revenue, balance_sheet_total) — die funktionieren nie

Antworte NUR mit einem JSON-Array:
```json
[
  {{"title": "Kurzer Button-Text", "query": "...", "filters": [...], "location": {{...}} | null}},
  ...
]
```"""


async def suggest_search_alternatives(
    query: str,
    filters: list[dict[str, Any]],
    location: dict[str, Any] | None,
    notes: str,
) -> list[dict[str, Any]]:
    """Generate 2-3 alternative search parameter sets when original search returned 0 results."""
    if not ANTHROPIC_API_KEY:
        return []

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = _ALTERNATIVES_PROMPT.format(
        query=query,
        filters=json.dumps(filters, ensure_ascii=False),
        location=json.dumps(location, ensure_ascii=False) if location else "null (bundesweit)",
        notes=notes,
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = response.content[0].text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            raw_text = "\n".join(lines)

        alternatives = json.loads(raw_text)
        if not isinstance(alternatives, list):
            logger.error("Alternatives response is not a list: %s", raw_text)
            return []

        # Ensure each alternative has required fields
        for alt in alternatives:
            alt.setdefault("query", query)
            alt.setdefault("filters", [{"field": "status", "value": "active"}])
            alt.setdefault("location", None)
            alt.setdefault("title", "Alternative Suche")

        logger.info("Generated %d search alternatives", len(alternatives))
        return alternatives[:3]

    except Exception as e:
        logger.error("Failed to generate search alternatives: %s", e)
        return []
