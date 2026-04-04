"""Longlist — Branded HTML email templates matching longlist.email website design."""
from __future__ import annotations

import html
import re

from config import PACKAGES

# Brand design tokens (from website CSS variables)
_BRAND_GREEN = "#1b4332"
_BRAND_GREEN_HOVER = "#2d6a4f"
_BRAND_GREEN_LIGHT = "#40916c"
_BG_PRIMARY = "#faf9f6"
_BG_SUNKEN = "#f5f3ef"
_TEXT_MAIN = "#18181b"
_TEXT_MUTED = "#71717a"
_TEXT_LIGHT = "#ffffff"
_BORDER_SUBTLE = "rgba(24,24,27,0.08)"
_BORDER_STRONG = "rgba(24,24,27,0.16)"
_FONT_DISPLAY = "'Georgia', 'Times New Roman', serif"
_FONT_BASE = "'Helvetica Neue', Helvetica, Arial, sans-serif"

_PACKAGE_ORDER = ("basis", "kontakt", "deep_data")


def _fmt_eur(cents: int) -> str:
    """Format EUR cents as German price (e.g. 150 → '1,50 €')."""
    eur = cents / 100
    if eur == int(eur):
        return f"{int(eur)},00 €"
    return f"{eur:.2f} €".replace(".", ",")


def _email_wrapper(inner_html: str) -> str:
    """Wrap content in a branded email layout."""
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:{_BG_PRIMARY};font-family:{_FONT_BASE};-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:{_BG_PRIMARY};">
  <tr><td align="center" style="padding:32px 16px;">
    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;">
      <!-- Logo -->
      <tr><td style="padding:0 0 24px 0;">
        <span style="font-family:{_FONT_DISPLAY};font-size:22px;color:{_TEXT_MAIN};letter-spacing:-0.5px;">
          <strong>Long</strong><span style="font-weight:300;">list</span>
        </span>
      </td></tr>
      <!-- Content Card -->
      <tr><td style="background-color:#ffffff;border-radius:12px;border:1px solid {_BORDER_SUBTLE};padding:32px 28px;box-shadow:0 2px 4px rgba(24,24,27,0.02);">
        {inner_html}
      </td></tr>
      <!-- Footer -->
      <tr><td style="padding:24px 0 0 0;text-align:center;">
        <p style="margin:0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};line-height:1.5;">
          Longlist — M&A Sourcing per E-Mail<br>
          © 2026 Longlist · <a href="https://longlist.email/impressum" style="color:{_TEXT_MUTED};text-decoration:underline;">Impressum</a> · <a href="https://longlist.email/datenschutz" style="color:{_TEXT_MUTED};text-decoration:underline;">Datenschutz</a>
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _markdown_to_html_inline(text: str) -> str:
    """Convert basic Markdown inline formatting to HTML.

    Handles: **bold**, *italic*, - list items.
    Must be called AFTER html.escape() since it injects HTML tags.
    """
    # Bold: **text** → <strong>text</strong>
    text = re.sub(
        r"\*\*(.+?)\*\*",
        rf'<strong style="font-weight:600;color:{_TEXT_MAIN};">\1</strong>',
        text,
    )
    # Italic: *text* → <em>text</em> (only single asterisks, not inside bold)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _is_markdown_table(lines: list[str]) -> bool:
    """Check if lines form a Markdown pipe table."""
    data_lines = [l for l in lines if l.strip() and not re.match(r"^\|[\s\-:|]+\|$", l.strip())]
    if len(data_lines) < 2:  # Need header + at least 1 body row
        return False
    return all(l.strip().startswith("|") and l.strip().endswith("|") for l in data_lines)


def _markdown_table_to_html(lines: list[str]) -> str:
    """Convert Markdown pipe-table lines into a styled HTML table."""
    rows: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip separator rows like |---|---|
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return ""

    header = rows[0]
    body = rows[1:]

    th_style = (
        f"padding:8px 12px;font-family:{_FONT_BASE};font-size:13px;font-weight:600;"
        f"color:{_TEXT_MAIN};border-bottom:2px solid {_BORDER_STRONG};"
        f"text-align:left;"
    )
    td_style = (
        f"padding:8px 12px;font-family:{_FONT_BASE};font-size:14px;"
        f"color:{_TEXT_MAIN};border-bottom:1px solid {_BORDER_SUBTLE};"
    )

    thead = "<tr>" + "".join(
        f'<th style="{th_style}">{_markdown_to_html_inline(html.escape(c))}</th>'
        for c in header
    ) + "</tr>"

    tbody_rows = []
    for row in body:
        tds = "".join(
            f'<td style="{td_style}">{_markdown_to_html_inline(html.escape(c))}</td>'
            for c in row
        )
        tbody_rows.append(f"<tr>{tds}</tr>")

    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"'
        f' style="margin:0 0 16px 0;border-collapse:collapse;">'
        f"<thead>{thead}</thead>"
        f'<tbody>{"".join(tbody_rows)}</tbody>'
        f"</table>"
    )


def plain_paragraphs_to_html(text: str) -> str:
    """Convert plain text paragraphs into styled HTML paragraphs.

    Supports Markdown-style **bold** and *italic* formatting,
    converts lines starting with '- ' into a simple list,
    and converts Markdown pipe tables into HTML tables.
    """
    text = (text or "").strip()
    if not text:
        return ""

    chunks = re.split(r"\n\s*\n", text)
    blocks: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.split("\n")

        # Check if this chunk is a Markdown table
        if _is_markdown_table(lines):
            blocks.append(_markdown_table_to_html(lines))
            continue

        # Check if this chunk is a list (all lines start with '- ')
        is_list = all(line.strip().startswith("- ") for line in lines if line.strip())

        if is_list:
            items = []
            for line in lines:
                line = line.strip()
                if line.startswith("- "):
                    item_text = html.escape(line[2:].strip())
                    item_text = _markdown_to_html_inline(item_text)
                    items.append(
                        f'<li style="margin:0 0 4px 0;font-family:{_FONT_BASE};'
                        f'font-size:15px;line-height:1.6;color:{_TEXT_MAIN};">{item_text}</li>'
                    )
            blocks.append(
                f'<ul style="margin:0 0 16px 0;padding-left:20px;">{"".join(items)}</ul>'
            )
        else:
            inner = html.escape(chunk)
            inner = _markdown_to_html_inline(inner)
            inner = inner.replace("\n", "<br>\n")
            blocks.append(
                f'<p style="margin:0 0 16px 0;font-family:{_FONT_BASE};'
                f'font-size:15px;line-height:1.6;color:{_TEXT_MAIN};">{inner}</p>'
            )
    return "\n".join(blocks)


def build_checkout_cta_plaintext(urls: dict[str, str], total_companies: int = 0) -> str:
    """Plaintext version of checkout CTAs."""
    lines = [
        "",
        "---",
        "Zahlung — bitte wählen Sie Ihr Paket:",
        "",
    ]
    for key in _PACKAGE_ORDER:
        pkg = PACKAGES[key]
        label = pkg["label"]
        url = urls.get(key, "#")
        if total_companies > 0:
            total = _fmt_eur(pkg["unit_price_eur_cents"] * total_companies)
            unit = _fmt_eur(pkg["unit_price_eur_cents"])
            lines.append(f"{label} ({unit}/Unternehmen × {total_companies} = {total}): {url}")
        else:
            lines.append(f"{label}: {url}")
    return "\n".join(lines)


def _tier_card(url: str, label: str, desc: str, unit_price_cents: int, total_companies: int, is_popular: bool = False) -> str:
    """Render a single tier card for the checkout CTA."""
    safe_href = html.escape(url, quote=True)
    unit = _fmt_eur(unit_price_cents)
    total = _fmt_eur(unit_price_cents * total_companies) if total_companies > 0 else ""

    popular_badge = ""
    if is_popular:
        popular_badge = (
            f'<span style="display:inline-block;background-color:{_BRAND_GREEN};color:{_TEXT_LIGHT};'
            f'font-family:{_FONT_BASE};font-size:11px;font-weight:600;padding:2px 10px;'
            f'border-radius:9999px;margin-bottom:8px;letter-spacing:0.3px;">Beliebt</span><br>'
        )

    price_line = f'<span style="font-family:{_FONT_DISPLAY};font-size:24px;font-weight:700;color:{_TEXT_MAIN};">{unit}</span>'
    price_line += f'<span style="font-family:{_FONT_BASE};font-size:13px;color:{_TEXT_MUTED};">/Unternehmen</span>'

    total_line = ""
    if total_companies > 0 and total:
        total_line = (
            f'<p style="margin:4px 0 0 0;font-family:{_FONT_BASE};font-size:13px;color:{_TEXT_MUTED};">'
            f'{total_companies} Unternehmen = <strong style="color:{_TEXT_MAIN};">{total}</strong></p>'
        )

    return f"""<td width="33%" style="vertical-align:top;padding:0 6px;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
    style="border:1px solid {_BORDER_STRONG};border-radius:12px;overflow:hidden;">
    <tr><td style="padding:16px 14px;text-align:center;">
      {popular_badge}
      <p style="margin:0 0 4px 0;font-family:{_FONT_BASE};font-size:14px;font-weight:700;color:{_TEXT_MAIN};">{html.escape(label)}</p>
      <p style="margin:0 0 10px 0;">{price_line}</p>
      {total_line}
      <p style="margin:10px 0 12px 0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};line-height:1.4;">{html.escape(desc)}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr><td style="border-radius:8px;background-color:{_BRAND_GREEN};text-align:center;">
          <a href="{safe_href}" target="_blank" rel="noopener noreferrer"
             style="display:block;padding:10px 8px;font-family:{_FONT_BASE};
                    font-size:13px;font-weight:600;color:{_TEXT_LIGHT};text-decoration:none;">
            {html.escape(label)} wählen
          </a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</td>"""


def build_checkout_cta_block(urls: dict[str, str], total_companies: int = 0) -> str:
    """Branded tier cards for Stripe checkout."""
    if total_companies == 0:
        return ""
    cards = []
    for key in _PACKAGE_ORDER:
        meta = PACKAGES[key]
        cards.append(_tier_card(
            url=urls.get(key, "#"),
            label=meta["label"],
            desc=meta["description"],
            unit_price_cents=meta["unit_price_eur_cents"],
            total_companies=total_companies,
            is_popular=(key == "kontakt"),
        ))

    return f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
  <tr><td>
    <p style="margin:0 0 16px 0;font-family:{_FONT_DISPLAY};font-size:18px;font-weight:700;color:{_TEXT_MAIN};">
      Paket wählen
    </p>
  </td></tr>
  <tr><td>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
      <tr>
        {cards[0]}
        {cards[1]}
        {cards[2]}
      </tr>
    </table>
  </td></tr>
</table>
<p style="margin:16px 0 0 0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};text-align:center;">
  Nach Zahlung erhalten Sie Ihre Longlist innerhalb von 24 Stunden per E-Mail.
</p>"""


def build_preview_email_html(body_plain: str, payment_urls: dict[str, str], total_companies: int = 0) -> str:
    """Full branded HTML for the offer email: prose + divider + tier cards."""
    prose = plain_paragraphs_to_html(body_plain)
    cta = build_checkout_cta_block(payment_urls, total_companies)
    # Visual divider between prose and CTA
    divider = f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;">
  <tr><td style="border-top:1px solid {_BORDER_SUBTLE};"></td></tr>
</table>""" if cta else ""
    inner = f'{prose}\n{divider}\n{cta}'
    return _email_wrapper(inner)


def _retry_button(url: str, title: str, total: int, preview_names: list[str]) -> str:
    """Single retry-search CTA card with button, result count, and preview names."""
    safe_href = html.escape(url, quote=True)
    safe_title = html.escape(title)
    preview_html = ""
    if preview_names:
        names = ", ".join(html.escape(n) for n in preview_names[:3])
        preview_html = f"""
    <p style="margin:6px 0 0 0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};line-height:1.4;">
      z.B. {names}
    </p>"""

    return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
  style="margin-bottom:12px;">
  <tr><td style="border:1px solid {_BORDER_STRONG};border-radius:10px;padding:16px 20px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
      <tr>
        <td style="vertical-align:middle;">
          <p style="margin:0;font-family:{_FONT_BASE};font-size:15px;font-weight:600;color:{_TEXT_MAIN};">
            {safe_title}
          </p>
          <p style="margin:4px 0 0 0;font-family:{_FONT_BASE};font-size:13px;color:{_TEXT_MUTED};">
            {total} Unternehmen gefunden
          </p>{preview_html}
        </td>
        <td style="vertical-align:middle;text-align:right;width:140px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr><td style="border-radius:8px;background-color:{_BRAND_GREEN};text-align:center;">
              <a href="{safe_href}" target="_blank" rel="noopener noreferrer"
                 style="display:block;padding:10px 18px;font-family:{_FONT_BASE};
                        font-size:13px;font-weight:600;color:{_TEXT_LIGHT};text-decoration:none;">
                Suche starten
              </a>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>
  </td></tr>
</table>"""


def build_no_results_email_html(
    body_plain: str,
    alternatives: list[dict],
    retry_urls: dict[str, str],
) -> str:
    """Branded HTML for no-results email with retry CTA buttons."""
    prose = plain_paragraphs_to_html(body_plain)

    alt_html = ""
    if alternatives:
        buttons = []
        for i, alt in enumerate(alternatives):
            key = f"v{i}"
            url = retry_urls.get(key, "#")
            buttons.append(_retry_button(
                url=url,
                title=alt.get("title", "Alternative Suche"),
                total=alt.get("total", 0),
                preview_names=alt.get("preview", []),
            ))

        alt_html = f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
  <tr><td>
    <p style="margin:0 0 16px 0;font-family:{_FONT_DISPLAY};font-size:18px;font-weight:700;color:{_TEXT_MAIN};">
      Alternative Suchen
    </p>
    <p style="margin:0 0 16px 0;font-family:{_FONT_BASE};font-size:14px;color:{_TEXT_MUTED};">
      Wir haben automatisch verwandte Suchen getestet. Per Klick starten Sie eine neue Recherche:
    </p>
  </td></tr>
  <tr><td>
    {"".join(buttons)}
  </td></tr>
</table>"""

    inner = f'{prose}\n{alt_html}'
    return _email_wrapper(inner)


def build_delivery_email_html(body_plain: str) -> str:
    """Branded HTML for delivery email — content only, no payment block."""
    inner = plain_paragraphs_to_html(body_plain)
    return _email_wrapper(inner)


# ---------------------------------------------------------------------------
# Smart Service Menu — email with CTA buttons for service selection
# ---------------------------------------------------------------------------

# Only longlist is active — other services disabled while we focus on search quality
_SERVICE_MENU_ITEMS = [
    {
        "key": "longlist",
        "label": "Longlist-Recherche",
        "desc": "Firmen nach Branche, Region und weiteren Kriterien suchen und anreichern.",
        "price": "Ab 1,50\u202f\u20ac/Firma",
        "use_case": "Ideal für: Marktanalyse, Wettbewerberrecherche, M&A-Longlist",
    },
]

# Disabled services — kept for future re-activation
_DISABLED_SERVICE_MENU_ITEMS = [
    {
        "key": "enrichment",
        "label": "Datenanreicherung",
        "desc": "Firmendaten, Kontakte & Finanzen für die genannte(n) Firma(en) recherchieren.",
        "price": "Ab 1,50\u202f\u20ac/Firma",
        "use_case": "Ideal für: Due-Diligence-Vorbereitung, Marktüberblick",
    },
    {
        "key": "sell_side",
        "label": "Käufersuche (Sell-Side)",
        "desc": "Potenzielle Käufer für Ihr Zielunternehmen identifizieren und kategorisieren.",
        "price": "Ab 1,50\u202f\u20ac/Käufer",
        "use_case": "Ideal für: Sell-Side Mandate, Käuferlisten",
    },
    {
        "key": "file_enrichment",
        "label": "Firmenliste anreichern",
        "desc": "Ihre Excel- oder CSV-Datei hochladen und Firmendaten anreichern lassen.",
        "price": "Ab 1,50\u202f\u20ac/Firma",
        "use_case": "Ideal für: Bestehende Listen vervollständigen",
    },
]


def _service_menu_card(
    item: dict,
    select_url: str,
    is_recommended: bool = False,
) -> str:
    """Render a single service option card."""
    safe_href = html.escape(select_url, quote=True)

    recommended_badge = ""
    border_color = _BORDER_STRONG
    if is_recommended:
        recommended_badge = (
            f'<span style="display:inline-block;background-color:{_BRAND_GREEN};color:{_TEXT_LIGHT};'
            f'font-family:{_FONT_BASE};font-size:11px;font-weight:600;padding:2px 10px;'
            f'border-radius:9999px;margin-bottom:8px;letter-spacing:0.3px;">Empfohlen</span><br>'
        )
        border_color = _BRAND_GREEN

    return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
  style="margin-bottom:12px;">
  <tr><td style="border:{'2px' if is_recommended else '1px'} solid {border_color};border-radius:10px;padding:20px 24px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
      <tr>
        <td style="vertical-align:top;">
          {recommended_badge}
          <p style="margin:0 0 4px 0;font-family:{_FONT_BASE};font-size:16px;font-weight:700;color:{_TEXT_MAIN};">
            {html.escape(item['label'])}
          </p>
          <p style="margin:0 0 6px 0;font-family:{_FONT_BASE};font-size:14px;color:{_TEXT_MAIN};line-height:1.5;">
            {html.escape(item['desc'])}
          </p>
          <p style="margin:0 0 4px 0;font-family:{_FONT_BASE};font-size:13px;color:{_TEXT_MUTED};">
            {html.escape(item['price'])} · {html.escape(item['use_case'])}
          </p>
        </td>
        <td style="vertical-align:middle;text-align:right;width:160px;padding-left:16px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr><td style="border-radius:8px;background-color:{_BRAND_GREEN};text-align:center;">
              <a href="{safe_href}" target="_blank" rel="noopener noreferrer"
                 style="display:block;padding:12px 20px;font-family:{_FONT_BASE};
                        font-size:13px;font-weight:600;color:{_TEXT_LIGHT};text-decoration:none;white-space:nowrap;">
                Auswählen
              </a>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>
  </td></tr>
</table>"""


def build_service_menu_email_html(
    body_plain: str,
    job_id: str,
    app_url: str,
    recommended_service: str | None = None,
    show_file_upload: bool = False,
) -> str:
    """Branded HTML for the Smart Service Menu email.

    Args:
        body_plain: Intro text (plain text, will be converted to HTML paragraphs).
        job_id: Job ID for building selection URLs.
        app_url: Base URL for the app (e.g. https://longlist-production.up.railway.app).
        recommended_service: Key of the recommended service (enrichment/sell_side/longlist/file_enrichment).
        show_file_upload: Whether to show the file upload option.
    """
    prose = plain_paragraphs_to_html(body_plain)

    items = [i for i in _SERVICE_MENU_ITEMS if show_file_upload or i["key"] != "file_enrichment"]

    # Sort so recommended is first
    if recommended_service:
        items = sorted(items, key=lambda i: i["key"] != recommended_service)

    cards = []
    for item in items:
        url = f"{app_url}/select/{job_id}/{item['key']}"
        cards.append(_service_menu_card(
            item=item,
            select_url=url,
            is_recommended=(item["key"] == recommended_service),
        ))

    menu_html = f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
  <tr><td>
    <p style="margin:0 0 16px 0;font-family:{_FONT_DISPLAY};font-size:18px;font-weight:700;color:{_TEXT_MAIN};">
      Welchen Service benötigen Sie?
    </p>
  </td></tr>
  <tr><td>
    {''.join(cards)}
  </td></tr>
</table>
<p style="margin:16px 0 0 0;font-family:{_FONT_BASE};font-size:12px;color:{_TEXT_MUTED};text-align:center;">
  Oder antworten Sie einfach auf diese E-Mail mit Ihrem Wunsch.
</p>"""

    divider = f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;">
  <tr><td style="border-top:1px solid {_BORDER_SUBTLE};"></td></tr>
</table>"""

    inner = f'{prose}\n{divider}\n{menu_html}'
    return _email_wrapper(inner)


def build_service_menu_plaintext(
    body_plain: str,
    job_id: str,
    app_url: str,
    recommended_service: str | None = None,
    show_file_upload: bool = False,
) -> str:
    """Plaintext version of the service menu email."""
    lines = [body_plain, "", "---", "", "Welchen Service benötigen Sie?", ""]
    items = [i for i in _SERVICE_MENU_ITEMS if show_file_upload or i["key"] != "file_enrichment"]
    for item in items:
        prefix = ">> " if item["key"] == recommended_service else "   "
        rec = " (Empfohlen)" if item["key"] == recommended_service else ""
        url = f"{app_url}/select/{job_id}/{item['key']}"
        lines.append(f"{prefix}{item['label']}{rec}")
        lines.append(f"   {item['desc']}")
        lines.append(f"   {item['price']} · {item['use_case']}")
        lines.append(f"   → {url}")
        lines.append("")
    lines.append("Oder antworten Sie einfach auf diese E-Mail mit Ihrem Wunsch.")
    return "\n".join(lines)
