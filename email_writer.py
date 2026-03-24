"""Longlist — Claude Call #2: Write delivery email for completed job."""
import logging

import anthropic
from config import ANTHROPIC_API_KEY

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


async def write_preview_email(
    total_companies: int,
    preview_names: list[str],
    search_summary: str,
    payment_urls: dict[str, str],
    service_type: str = "longlist",
) -> str:
    """
    Write the preview/offer email after initial search.
    Includes company count, preview names, and 3 Stripe payment links.
    """
    if not ANTHROPIC_API_KEY:
        # Fallback template
        return _preview_template(total_companies, preview_names, search_summary, payment_urls, service_type)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = f"""Schreibe eine Antwort-E-Mail für folgende Situation:

Service: {"Longlist-Recherche" if service_type == "longlist" else "Datenanreicherung"}
Suchergebnis: {total_companies} Unternehmen gefunden
Beispiel-Unternehmen: {', '.join(preview_names[:5])}
Suchzusammenfassung: {search_summary}

Zahlungslinks:
- BASIS: {payment_urls.get('basis', '#')}
- STANDARD: {payment_urls.get('standard', '#')}
- PREMIUM: {payment_urls.get('premium', '#')}

Paket-Beschreibungen:
- BASIS (Stammdaten): Firma, Adresse, Geschäftsführer, Website, Telefon
- STANDARD (+ Finanzen): zusätzlich Umsatz, Bilanz, Eigenkapital, Mitarbeiter
- PREMIUM (+ Gesellschafter & GF-Email): zusätzlich Eigentümerstruktur und verifizierte GF-E-Mail

Regeln:
- Nenne die genaue Anzahl gefundener Unternehmen
- Liste 3-5 Beispielunternehmen auf
- Stelle die 3 Pakete klar dar mit Preislinks
- Erwähne dass nach Zahlung die Daten innerhalb von 24h geliefert werden
- Kein Betreff nötig (wird als Reply gesendet)
- Sachlich, professionell, Sie-Form
"""

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
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
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    return response.content[0].text.strip()


def _preview_template(
    total: int,
    names: list[str],
    summary: str,
    urls: dict[str, str],
    service_type: str,
) -> str:
    """Fallback template when Claude API is unavailable."""
    preview = "\n".join(f"  • {n}" for n in names[:5])
    return f"""Sehr geehrte Damen und Herren,

vielen Dank für Ihre Anfrage. Basierend auf Ihren Kriterien ({summary}) haben wir {total} Unternehmen identifiziert.

Hier ein Auszug:
{preview}

Wählen Sie Ihr gewünschtes Datenpaket:

📋 BASIS — Stammdaten, Adresse, GF, Website, Telefon
→ {urls.get('basis', '#')}

📊 STANDARD — zusätzlich Umsatz, Bilanz, EK, Mitarbeiter
→ {urls.get('standard', '#')}

🏆 PREMIUM — zusätzlich Gesellschafter & verifizierte GF-Email
→ {urls.get('premium', '#')}

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
