"""Longlist — Claude Call #2: Write delivery email for completed job."""
from __future__ import annotations

import logging

import anthropic
from config import ANTHROPIC_API_KEY, PACKAGES

logger = logging.getLogger("longlist.email_writer")

SYSTEM_PROMPT = """Du bist der E-Mail-Verfasser von Longlist, einem Research-as-a-Service für deutsche M&A-Berater.

Schreibe professionelle, sachliche E-Mails in formalem Deutsch (Sie-Form).

Stil:
- Kurz und präzise, keine Floskeln
- Sachlich-professionell, nicht zu förmlich
- Klar strukturiert
- Immer "Mit freundlichen Grüßen" als Abschluss
- Unterschrift: "Max Zwisler\nLonglist Research"
"""


def _fmt_eur(cents: int) -> str:
    """Format EUR cents as German price string (e.g. 150 → '1,50 €')."""
    eur = cents / 100
    if eur == int(eur):
        return f"{int(eur)},00 €"
    return f"{eur:.2f} €".replace(".", ",")


def _build_pricing_info(total_companies: int) -> str:
    """Build a pricing table string for the email prompt."""
    lines = []
    for key in ("basis", "kontakt", "deep_data"):
        pkg = PACKAGES[key]
        unit = _fmt_eur(pkg["unit_price_eur_cents"])
        total = _fmt_eur(pkg["unit_price_eur_cents"] * total_companies)
        lines.append(
            f"- {pkg['label']} ({unit}/Unternehmen × {total_companies} = {total}): "
            f"{pkg['description_long']}"
        )
    return "\n".join(lines)


async def write_preview_email(
    total_companies: int,
    preview_names: list[str],
    search_summary: str,
    payment_urls: dict[str, str],
    service_type: str = "longlist",
) -> str:
    """
    Write the preview/offer email after initial search.
    Includes company count, preview names, and per-company pricing; payment URLs are appended in main.py.
    """
    _ = payment_urls  # Checkout URLs appended in main.py (HTML + plaintext CTA)

    if not ANTHROPIC_API_KEY:
        return _preview_template(total_companies, preview_names, search_summary, service_type)

    pricing_info = _build_pricing_info(total_companies)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = f"""Schreibe eine Antwort-E-Mail auf eine Recherche-Anfrage.

**Kontext:**
Service: {"Longlist-Recherche (Suche nach Kriterien)" if service_type == "longlist" else "Datenanreicherung (konkrete Firmennamen)"}
Suchergebnis: {total_companies} Unternehmen gefunden
Beispiel-Unternehmen: {', '.join(preview_names[:5])}
Recherche-Zusammenfassung: {search_summary}

**Pakete mit Preisen:**
{pricing_info}

**Struktur der E-Mail (genau in dieser Reihenfolge):**
1. Kurze Begrüßung + Bestätigung der Anfrage (1 Satz)
2. **Ergebnis:** Anzahl gefundener Unternehmen + 3-5 Beispiele als Aufzählung
3. **Pakete:** Alle drei Pakete mit Stückpreis UND Gesamtpreis klar darstellen. Hebe die Unterschiede zwischen den Paketen hervor (nicht nur Preise, sondern welche Datenpunkte man bekommt)
4. **Nächster Schritt:** Hinweis dass die Paketauswahl direkt unter der E-Mail möglich ist
5. **Lieferversprechen:** Formatierte Excel-Datei innerhalb von 24 Stunden nach Zahlung
6. Abschluss mit Kontaktangebot bei Rückfragen

**Stilregeln:**
- KEINE URLs oder Links im Text — Zahlungsbuttons werden automatisch unter der E-Mail angefügt
- KEINE Paketpreise wiederholen die schon in den Buttons stehen — fokussiere auf den Mehrwert jedes Pakets
- KEINE Markdown-Tabellen (Pipe-Syntax) — verwende Aufzählungen oder Fließtext für Paketübersichten
- Sachlich, professionell, Sie-Form
- Maximal 200 Wörter — kurz und auf den Punkt
"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


async def write_delivery_email(
    enriched_count: int,
    package: str,
    search_summary: str,
) -> str:
    """Write the delivery email when the Excel is ready."""
    if not ANTHROPIC_API_KEY:
        return _delivery_template(enriched_count, package, search_summary)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    from config import PACKAGES
    pkg_label = PACKAGES.get(package, {}).get("label", package)

    user_msg = f"""Schreibe eine Lieferungs-E-Mail für eine abgeschlossene Recherche.

**Kontext:**
Paket: {pkg_label}
Anzahl Unternehmen: {enriched_count}
Recherche: {search_summary}

**Struktur der E-Mail:**
1. Bestätigung: Excel-Datei ist im Anhang, {enriched_count} Unternehmen im Paket "{pkg_label}"
2. **Was Sie erhalten haben:** Kurze Aufzählung der enthaltenen Datenpunkte je nach Paket
3. **Empfohlene nächste Schritte:** 2-3 konkrete Vorschläge was der Berater mit den Daten tun kann (z.B. "Targets priorisieren", "GF direkt kontaktieren", "Finanzdaten in Ihre Bewertungsmodelle übernehmen")
4. Rechnungshinweis: "Die Rechnung erhalten Sie separat per E-Mail von Stripe."
5. Kontaktangebot: Bei Rückfragen oder für eine Folgerecherche

**Stilregeln:**
- Maximal 150 Wörter
- Sachlich, professionell, Sie-Form
- Betone den Mehrwert der gelieferten Daten
"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


async def write_no_results_email(
    search_summary: str,
    query: str = "",
    filters: list | None = None,
    location: dict | None = None,
) -> str:
    """Write a follow-up email when the search returned 0 results."""
    # Build human-readable criteria summary
    criteria_parts = []
    if query:
        criteria_parts.append(f"Suchbegriff: {query}")
    for f in (filters or []):
        field = f.get("field", "")
        value = f.get("value", "")
        if field == "status":
            continue  # Skip generic status filter
        if field == "employees":
            criteria_parts.append(f"Mitarbeiter: {f.get('min', '?')}–{f.get('max', '?')}")
        elif field == "legal_form":
            criteria_parts.append(f"Rechtsform: {value}")
        elif field == "industry_codes":
            criteria_parts.append(f"Branchencode (WZ): {value}")
        else:
            criteria_parts.append(f"{field}: {value}")
    if location:
        criteria_parts.append(f"Standort: Radius {location.get('radius', '?')} km")
    criteria_str = "\n".join(f"  • {c}" for c in criteria_parts) if criteria_parts else "  (keine spezifischen Filter)"

    if not ANTHROPIC_API_KEY:
        return _no_results_template(search_summary, criteria_str)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = f"""Die Longlist-Recherche hat 0 Ergebnisse ergeben. Schreibe eine freundliche Rückfrage-E-Mail.

Suchzusammenfassung: {search_summary}
Verwendete Kriterien:
{criteria_str}

Regeln:
- Erkläre kurz, dass die Kombination der Suchkriterien keine Treffer ergeben hat
- Liste die verwendeten Kriterien auf
- Schlage konkret vor, was angepasst werden könnte (Region erweitern, Branchencode ändern, Mitarbeiterfilter lockern)
- Biete an, die Suche mit angepassten Kriterien erneut durchzuführen
- Betone, dass keine Kosten entstanden sind
- Sachlich, professionell, Sie-Form
- KEINE Zahlungslinks, KEINE Paketbeschreibungen
"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


def _no_results_template(summary: str, criteria: str) -> str:
    """Fallback template when Claude API is unavailable for no-results email."""
    return f"""Sehr geehrte Damen und Herren,

vielen Dank für Ihre Anfrage ({summary}).

Leider hat die Kombination Ihrer Suchkriterien keine Treffer ergeben:
{criteria}

Es sind Ihnen keine Kosten entstanden.

Wir empfehlen, die Suchanfrage mit angepassten Kriterien zu wiederholen — etwa durch Erweiterung der geografischen Region oder Lockerung einzelner Filter.

Gerne führen wir eine neue Recherche für Sie durch. Antworten Sie einfach auf diese E-Mail mit Ihren angepassten Kriterien.

Mit freundlichen Grüßen
Max Zwisler
Longlist Research"""


def _preview_template(
    total: int,
    names: list[str],
    summary: str,
    service_type: str,
) -> str:
    """Fallback template when Claude API is unavailable (no payment URLs — added in main)."""
    preview = "\n".join(f"  • {n}" for n in names[:5])
    svc = "Longlist-Recherche" if service_type == "longlist" else "Datenanreicherung"

    # Build pricing lines
    pricing_lines = []
    for key in ("basis", "kontakt", "deep_data"):
        pkg = PACKAGES[key]
        unit = _fmt_eur(pkg["unit_price_eur_cents"])
        total_price = _fmt_eur(pkg["unit_price_eur_cents"] * total)
        pricing_lines.append(
            f"• {pkg['label']} — {pkg['description']} ({unit}/Unternehmen, gesamt {total_price})"
        )
    pricing_block = "\n".join(pricing_lines)

    return f"""Sehr geehrte Damen und Herren,

vielen Dank für Ihre Anfrage. Basierend auf Ihren Kriterien ({summary}) haben wir {total} Unternehmen identifiziert ({svc}).

Hier ein Auszug:
{preview}

Wir bieten drei Datenpakete:

{pricing_block}

Die Zahlung können Sie über die Schaltflächen unter diesem Text auslösen.

Nach Zahlungseingang liefern wir Ihnen die vollständige Excel-Datei innerhalb von 24 Stunden.

Mit freundlichen Grüßen
Max Zwisler
Longlist Research"""


def _delivery_template(count: int, package: str, summary: str) -> str:
    """Fallback template for delivery email."""
    return f"""Sehr geehrte Damen und Herren,

anbei erhalten Sie Ihre Longlist mit {count} Unternehmen (Paket {package.upper()}).

Recherche: {summary}

Die Rechnung erhalten Sie separat per E-Mail von Stripe.

Bei Rückfragen stehe ich Ihnen gerne zur Verfügung.

Mit freundlichen Grüßen
Max Zwisler
Longlist Research"""
