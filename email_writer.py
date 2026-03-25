"""Longlist — Claude Call #2: Write delivery email for completed job."""
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

    user_msg = f"""Schreibe eine Antwort-E-Mail für folgende Situation:

Service: {"Longlist-Recherche" if service_type == "longlist" else "Datenanreicherung"}
Suchergebnis: {total_companies} Unternehmen gefunden
Beispiel-Unternehmen: {', '.join(preview_names[:5])}
Suchzusammenfassung: {search_summary}

Paket-Beschreibungen mit Preisen (pro Unternehmen × Anzahl = Gesamtpreis):
{pricing_info}

Regeln:
- Nenne die genaue Anzahl gefundener Unternehmen
- Liste 3-5 Beispielunternehmen auf
- Stelle die 3 Pakete klar dar (Basis, Kontakt, Deep Data) — mit dem Preis pro Unternehmen UND dem Gesamtpreis
- Keine URLs, keine http(s)-Adressen — Zahlungslinks werden separat angefügt
- Erwähne dass nach Zahlung die Daten innerhalb von 24h geliefert werden
- Kein Betreff nötig (wird als Reply gesendet)
- Sachlich, professionell, Sie-Form
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

    user_msg = f"""Schreibe eine Lieferungs-E-Mail:

Paket: {package.upper()}
Anzahl Unternehmen: {enriched_count}
Recherche: {search_summary}

Regeln:
- Bestätige die Lieferung der Excel-Datei im Anhang
- Nenne Anzahl der Unternehmen und das gewählte Paket
- Biete an, bei Rückfragen zur Verfügung zu stehen
- Erwähne: "Die Rechnung erhalten Sie separat per E-Mail von Stripe."
- Kurz und sachlich
"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


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
