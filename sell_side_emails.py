"""Longlist — Email templates for sell-side buyer longlist service."""
import html
import logging
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY
from email_html import (
    _BORDER_STRONG,
    _BRAND_GREEN,
    _FONT_BASE,
    _FONT_DISPLAY,
    _TEXT_LIGHT,
    _TEXT_MAIN,
    _TEXT_MUTED,
    _email_wrapper,
    plain_paragraphs_to_html,
)

logger = logging.getLogger("longlist.sell_side_emails")

_SYSTEM = """Du bist der E-Mail-Verfasser von Longlist, einem Research-as-a-Service für deutsche M&A-Berater.
Schreibe professionelle, sachliche E-Mails in formalem Deutsch (Sie-Form).
Stil: Kurz und präzise, sachlich-professionell, klar strukturiert.
Unterschrift: "Max Zwisler\nLonglist Research"
"""


async def write_buyer_groups_email(
    target_analysis: dict[str, Any],
    buyer_groups: list[dict[str, Any]],
) -> str:
    """Write the buyer groups overview email (Email 2 in sell-side flow)."""
    target_name = target_analysis.get("name", "Zielunternehmen")
    target_summary = target_analysis.get("summary", "")
    industry = target_analysis.get("industry", "")

    groups_text = ""
    total_available = 0
    for g in buyer_groups:
        avail = g.get("available", 0)
        total_available += avail
        preview = g.get("preview_names", [])
        preview_str = f" (z.B. {', '.join(preview[:3])})" if preview else ""
        groups_text += f"- {g['name']}: {avail} Unternehmen verfügbar{preview_str}\n"

    if not ANTHROPIC_API_KEY:
        return _buyer_groups_template(target_name, target_summary, groups_text, total_available)

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"""Schreibe eine E-Mail mit den Ergebnissen unserer Käufergruppen-Analyse.

**Zielunternehmen:** {target_name} ({industry})
**Zusammenfassung:** {target_summary}

**Identifizierte Käufergruppen:**
{groups_text}

**Gesamt verfügbar:** {total_available} Unternehmen

**Struktur:**
1. Kurze Begrüßung + Bestätigung dass die Analyse abgeschlossen ist
2. Zusammenfassung des Zielunternehmens (1-2 Sätze)
3. Auflistung der Käufergruppen mit Beschreibung und Verfügbarkeit
4. Aufforderung: "Bitte antworten Sie mit Ihrer gewünschten Zusammensetzung"
5. Beispiel: "z.B. '60 Strategische, 40 Angrenzende, 20 PE'"
6. Hinweis: "Es sind Ihnen noch keine Kosten entstanden."
7. Abschluss

**Regeln:**
- KEINE Links, URLs oder Zahlungsbuttons
- Maximal 250 Wörter
- Sachlich, professionell, Sie-Form
"""}],
    )
    return response.content[0].text.strip()


async def write_sell_side_offer_email(
    target_name: str,
    selection: list[dict],
    buyer_groups: list[dict],
    total_companies: int,
) -> str:
    """Write the offer email after buyer group selection (with Stripe links)."""
    selected_summary = ""
    for s in selection:
        idx = s.get("group_index", 0)
        if idx < len(buyer_groups):
            group_name = buyer_groups[idx].get("name", "Gruppe")
            selected_summary += f"- {group_name}: {s['count']} Unternehmen\n"

    if not ANTHROPIC_API_KEY:
        return f"Ihre Auswahl für {target_name}: {total_companies} Unternehmen. Bitte wählen Sie ein Paket."

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"""Schreibe eine Angebots-E-Mail für die Sell-Side Buyer-Longlist.

**Zielunternehmen:** {target_name}
**Gewählte Zusammensetzung:**
{selected_summary}
**Gesamt:** {total_companies} Unternehmen

**Struktur:**
1. Bestätigung der Auswahl
2. Paketauswahl-Hinweis (Buttons folgen unter der E-Mail)
3. Lieferversprechen: Excel mit kategorisierten Tabs innerhalb 24h
4. Kurz und sachlich

**Regeln:**
- KEINE URLs oder Links — Zahlungsbuttons werden automatisch angefügt
- Maximal 100 Wörter
"""}],
    )
    return response.content[0].text.strip()


def _buyer_group_card(name: str, description: str, available: int, preview_names: list[str]) -> str:
    """Single buyer group card for the overview email."""
    safe_name = html.escape(name)
    safe_desc = html.escape(description)
    preview_html = ""
    if preview_names:
        names = ", ".join(html.escape(n) for n in preview_names[:3])
        preview_html = f"""
    <p style="margin:4px 0 0 0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};line-height:1.4;">
      z.B. {names}
    </p>"""

    return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
  style="margin-bottom:10px;">
  <tr><td style="border:1px solid {_BORDER_STRONG};border-radius:10px;padding:14px 18px;">
    <p style="margin:0;font-family:{_FONT_BASE};font-size:15px;font-weight:600;color:{_TEXT_MAIN};">
      {safe_name}
    </p>
    <p style="margin:4px 0 0 0;font-family:{_FONT_BASE};font-size:13px;color:{_TEXT_MUTED};">
      {safe_desc}
    </p>
    <p style="margin:6px 0 0 0;font-family:{_FONT_BASE};font-size:14px;font-weight:600;color:{_BRAND_GREEN};">
      {available} Unternehmen verfügbar
    </p>{preview_html}
  </td></tr>
</table>"""


def build_buyer_groups_email_html(
    body_plain: str,
    buyer_groups: list[dict[str, Any]],
) -> str:
    """Branded HTML for buyer groups overview email — NO payment links."""
    prose = plain_paragraphs_to_html(body_plain)

    cards = ""
    for g in buyer_groups:
        cards += _buyer_group_card(
            name=g.get("name", ""),
            description=g.get("description", ""),
            available=g.get("available", 0),
            preview_names=g.get("preview_names", []),
        )

    groups_section = f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
  <tr><td>
    <p style="margin:0 0 16px 0;font-family:{_FONT_DISPLAY};font-size:18px;font-weight:700;color:{_TEXT_MAIN};">
      Identifizierte Käufergruppen
    </p>
  </td></tr>
  <tr><td>
    {cards}
  </td></tr>
  <tr><td style="padding-top:16px;">
    <p style="margin:0;font-family:{_FONT_BASE};font-size:14px;color:{_TEXT_MAIN};font-weight:600;">
      Nächster Schritt:
    </p>
    <p style="margin:6px 0 0 0;font-family:{_FONT_BASE};font-size:14px;color:{_TEXT_MUTED};">
      Antworten Sie auf diese E-Mail mit Ihrer gewünschten Zusammensetzung,
      z.B. "60 Strategische, 40 Angrenzende, 20 PE" oder "150 gesamt".
    </p>
  </td></tr>
</table>"""

    inner = f'{prose}\n{groups_section}'
    return _email_wrapper(inner)


def _buyer_groups_template(
    target_name: str,
    summary: str,
    groups_text: str,
    total: int,
) -> str:
    """Fallback template without Claude."""
    return f"""Sehr geehrte Damen und Herren,

unsere Analyse von {target_name} ist abgeschlossen.
{summary}

Wir haben folgende Käufergruppen identifiziert:

{groups_text}

Gesamt: {total} Unternehmen verfügbar.

Bitte antworten Sie mit Ihrer gewünschten Zusammensetzung,
z.B. "60 Strategische, 40 Angrenzende, 20 PE = 120 gesamt".

Es sind Ihnen noch keine Kosten entstanden.

Mit freundlichen Grüßen
Max Zwisler
Longlist Research"""
