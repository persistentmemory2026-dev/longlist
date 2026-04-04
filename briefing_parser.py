"""Longlist — Claude Call #1: Parse M&A briefing email into structured JSON."""
from __future__ import annotations

import json
import logging
from typing import Any

from config import ANTHROPIC_API_KEY
from ai_client import create_message

logger = logging.getLogger("longlist.parser")

SYSTEM_PROMPT = """Du bist der Briefing-Parser von Longlist, einem Research-as-a-Service für deutsche M&A-Berater.

Deine Aufgabe: Analysiere die eingehende E-Mail und extrahiere strukturierte Suchparameter für die OpenRegister API.

## Service-Typ

Setze service_type IMMER auf "longlist". Wir bieten aktuell nur Longlist-Recherche an.
Wenn der Kunde konkrete Firmennamen nennt, setze sie trotzdem in "company_list" — wir nutzen das als Kontext.

Bestimme eine Konfidenz (0.0 bis 1.0) wie gut du die Suchanfrage verstehst:
- 0.95+: Klare Branche + Region + ggf. Rechtsform → direkte Verarbeitung
- 0.80-0.95: Branche klar, Details etwas unklar
- 0.50-0.80: Ambig — unklar was genau gesucht wird
- <0.50: Sehr unklar

## Entscheidung 2: Suchparameter extrahieren

Gib ein JSON-Objekt zurück mit genau dieser Struktur:

```json
{
  "service_type": "longlist" | "enrichment" | "sell_side",
  "confidence": 0.85,
  "target_company_url": "https://zielunternehmen.de" | null,
  "target_company_name": "Zielunternehmen GmbH" | null,
  "desired_count": 200 | null,
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

## Wie die OpenRegister-Suche WIRKLICH funktioniert (verifiziert mit Live-API)

Es gibt ZWEI Hauptwerkzeuge — `query` und `purpose keywords`. Sie suchen an VERSCHIEDENEN Stellen:
- `query`: sucht im FIRMENNAMEN (z.B. "Maschinenbau" findet "H. F. Meyer Maschinenbau GmbH")
- `purpose keywords`: sucht im UNTERNEHMENSGEGENSTAND (z.B. "Software" findet Firmen die Software entwickeln, auch wenn "Software" nicht im Namen steht)

### Drei Suchstrategien — wähle je nach Anfrage die beste

**Strategie A — Breit (Standard für Industrie/Handwerk):**
Wenn der Branchenbegriff typischerweise im Firmennamen vorkommt (Maschinenbau, Bäckerei, Immobilien).
→ Nutze `query` als Hauptwerkzeug + sichere Filter.
Beispiel: "Maschinenbauunternehmen in Bayern" → query="Maschinenbau" + location Bayern

**Strategie B — Präzision (wenn Kunde spezifische Tätigkeiten nennt):**
Wenn der Kunde eine konkrete Tätigkeit beschreibt (CNC-Fertigung, Kältetechnik, Spritzguss).
→ Nutze `query` für die Branche + `purpose keywords` für die spezifische Tätigkeit.
Beispiel: "CNC-Fräser im Maschinenbau" → query="Maschinenbau" + purpose keywords=["CNC", "Fräsen"]
ACHTUNG: Diese Kombination ist SEHR präzise (wenige Ergebnisse). Nur verwenden wenn Kunde explizit spezifisch sucht.

**Strategie C — Maximale Abdeckung (für Dienstleistungen/IT/Beratung):**
Wenn der Branchenbegriff SELTEN im Firmennamen vorkommt (Software, Beratung, Logistik).
→ Nutze `purpose keywords` als Hauptwerkzeug (OHNE query) + sichere Filter.
Beispiel: "Softwareunternehmen in NRW" → purpose keywords=["Software", "Softwareentwicklung"] + location NRW
WICHTIG: purpose keywords nutzt OR-Logik — mehr Keywords = mehr Ergebnisse! Gib 2-3 Synonyme an.

### Wann welche Strategie?

| Branche | Strategie | Grund |
|---------|-----------|-------|
| Maschinenbau, Bäckerei, Immobilien, Handwerk | A (query) | Begriff steht oft im Firmennamen |
| Software, IT, Beratung, Marketing, Dienstleistung | C (purpose keywords) | Begriff steht selten im Firmennamen, aber im Unternehmensgegenstand |
| Spezifische Tätigkeit (CNC, Spritzguss, Kältetechnik) | B (query + purpose) | Branche im Namen + Tätigkeit im Gegenstand |

### Filter-Sicherheitsranking

✅ SICHERE Filter (verwende großzügig):
- status: "active" — IMMER setzen, filtert 48% aufgelöste Firmen
- legal_form: "gmbh", "ag", "kg", etc. — sanfte Einschränkung (behält ~77%)
- incorporated_at: {"max": "2000-01-01"} — gut für "etabliert" (behält ~51%)
- location: {"latitude": ..., "longitude": ..., "radius": ...} — proportionale Einschränkung

⚠️ MODERATE Filter (nur wenn Kunde explizit danach fragt):
- has_representative_owner: "true" — inhabergeführt (behält ~39%)
- youngest_owner_age: {"min": "60"} — GF über 60 (behält nur ~14%)
- is_family_owned: "true" — Familienunternehmen (behält nur ~11%)
- has_sole_owner: "true" — Alleingesellschafter

❌ NIEMALS als Filter verwenden (Daten zu lückenhaft, zerstört Ergebnisse):
- employees — NUR 2% ABDECKUNG! "50-500 Mitarbeiter" → 98% der Firmen fallen weg
- industry_codes — Unzuverlässige WZ-Code-Zuordnung, viele Firmen ohne Codes
- revenue, balance_sheet_total, capital_amount — kaum Daten vorhanden
Wenn der Kunde Mitarbeiter-/Umsatz-/Finanzkriterien nennt, schreibe sie in "notes" aber NIEMALS in filters.

### purpose keywords — Syntax

RICHTIG: {"field": "purpose", "keywords": ["Keyword1", "Keyword2"]}
- "keywords" nutzt OR-Logik: mehr Keywords = MEHR Ergebnisse (nicht weniger!)
- Verwende 3-5 deutsche Synonyme für beste Abdeckung (3 Keywords = +50%, 6 Keywords = +160% vs. 1 Keyword)
- FALSCH: {"field": "purpose", "value": "..."} — das macht exakten Match und liefert fast nichts!

### WICHTIG: location ist KEIN Filter!
Location gehört NICHT in das filters-Array! Location ist ein separates Top-Level-Feld:
- RICHTIG: "location": {"latitude": 48.8, "longitude": 11.5, "radius": 150.0}
- FALSCH: "filters": [{"field": "location", ...}] ← DAS FUNKTIONIERT NICHT!

### KRITISCH: Deutsche Komposita IMMER aufspalten!

Deutsche Komposita (zusammengesetzte Wörter) funktionieren SCHLECHT als einzelnes Keyword.
IMMER in Bestandteile aufspalten UND Synonyme hinzufügen:

- "Werkzeugmaschine" → ["Werkzeug", "Maschine", "Werkzeugbau"] (1 vs. 1.451 Ergebnisse!)
- "Kunststoffverarbeitung" → ["Kunststoff", "Spritzguss", "Extrusion", "Kunststoffverarbeitung"]
- "Lebensmittelherstellung" → ["Lebensmittel", "Nahrungsmittel", "Herstellung"]
- "Softwareentwicklung" → ["Software", "Softwareentwicklung", "Programmierung", "IT-Dienstleistung"]
- "Metallverarbeitung" → ["Metall", "Metallverarbeitung", "Metallbau", "Stahlbau"]

Generelle Regel: Kompositum beibehalten + Bestandteile + 2-3 Synonyme = optimale Abdeckung

### WICHTIGE Regeln
1. Maximal 3 Filter gleichzeitig (jeder Filter halbiert die Ergebnisse grob)
2. NIEMALS industry_codes verwenden — WZ-Codes sind unzuverlässig zugeordnet
3. NIEMALS employees als Filter — nur 2% der Firmen haben diese Daten
4. NIEMALS query UND purpose keywords für DENSELBEN Begriff — das doppelt-filtert und killt Ergebnisse
5. Bei Strategie C (purpose keywords ohne query): es kommen trotzdem sinnvolle Ergebnisse, kein query nötig

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
- Fehlender Umsatz (→ weglassen, in notes schreiben)
- Fehlender Mitarbeiterzahl (→ weglassen, in notes schreiben)

## Default-Verhalten
- Immer status: "active" setzen
- Wenn keine spezifischen Datenpunkte genannt → alle Basis-Daten liefern
- Im Zweifel WENIGER Filter → mehr Ergebnisse → Kunde kann verfeinern
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
    user_msg = USER_PROMPT_TEMPLATE.format(
        sender=sender,
        subject=subject,
        body=body,
    )

    logger.info("Parsing briefing from %s: %s", sender, subject)

    raw_text = await create_message(
        system=SYSTEM_PROMPT,
        user_msg=user_msg,
        max_tokens=2000,
    )

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
    parsed.setdefault("confidence", 0.5)
    parsed.setdefault("target_company_url", None)
    parsed.setdefault("target_company_name", None)
    parsed.setdefault("desired_count", None)
    parsed.setdefault("query", "")
    parsed.setdefault("filters", [])
    parsed.setdefault("location", None)
    parsed.setdefault("company_list", None)
    parsed.setdefault("notes", "")
    parsed.setdefault("needs_clarification", False)
    parsed.setdefault("clarification_question", None)

    # Force longlist — only service currently active
    parsed["service_type"] = "longlist"

    # Ensure confidence is a float
    try:
        parsed["confidence"] = float(parsed["confidence"])
    except (TypeError, ValueError):
        parsed["confidence"] = 0.5

    # Always ensure status: active filter is present
    has_status = any(f.get("field") == "status" for f in parsed["filters"])
    if not has_status:
        parsed["filters"].insert(0, {"field": "status", "value": "active"})

    logger.info("Parsed briefing: service=%s, confidence=%.2f, query=%s, %d filters",
                parsed["service_type"], parsed["confidence"], parsed["query"], len(parsed["filters"]))

    return parsed


_ALTERNATIVES_PROMPT = """Die folgende Longlist-Suche hat 0 Treffer ergeben. Schlage 2-3 alternative Suchparameter-Sets vor, die wahrscheinlich Ergebnisse liefern.

Originale Suchparameter:
- query: {query}
- filters: {filters}
- location: {location}
- Kundenwunsch: {notes}

Strategien (wähle die 2-3 passendsten):
1. Suchbegriff variieren (Synonyme, verwandte Begriffe, kürzere Terme)
2. Region erweitern (größerer Radius oder ganz weglassen)
3. Restriktive Filter entfernen (employees, is_family_owned, youngest_owner_age etc.)
4. Filter-Kombination vereinfachen (weniger Filter = mehr Treffer)

WICHTIG:
- Der query-Term ist der WICHTIGSTE Parameter — er sucht im Firmennamen
- Jede Alternative MUSS sich deutlich von der Original-Suche unterscheiden
- Jede Alternative braucht einen kurzen deutschen "title" (max 40 Zeichen) für den Button-Text
- Verwende dasselbe JSON-Schema wie die Original-Suche
- Immer status: "active" als Filter beibehalten
- NIEMALS diese Filter verwenden: employees, industry_codes, revenue, balance_sheet_total, capital_amount
- ALLE Filter-Werte MÜSSEN Strings sein (z.B. "50" nicht 50, "true" nicht true)
- Mindestens eine Alternative MUSS location auf null setzen (bundesweite Suche)
- Mindestens eine Alternative MUSS den query-Term durch ein Synonym/verwandten Begriff ersetzen
- Halte Filter minimal — max 2-3 Filter, je weniger desto mehr Treffer

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
    user_msg = _ALTERNATIVES_PROMPT.format(
        query=query,
        filters=json.dumps(filters, ensure_ascii=False),
        location=json.dumps(location, ensure_ascii=False) if location else "null (bundesweit)",
        notes=notes,
    )

    try:
        raw_text = await create_message(
            system=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_tokens=2000,
        )
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
