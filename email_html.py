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


def plain_paragraphs_to_html(text: str) -> str:
    """Convert plain text paragraphs into styled HTML paragraphs.

    Supports Markdown-style **bold** and *italic* formatting, and
    converts lines starting with '- ' into a simple list.
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
    """Full branded HTML for the offer email: prose + tier cards."""
    prose = plain_paragraphs_to_html(body_plain)
    cta = build_checkout_cta_block(payment_urls, total_companies)
    inner = f'{prose}\n{cta}'
    return _email_wrapper(inner)


def build_delivery_email_html(body_plain: str) -> str:
    """Branded HTML for delivery email — content only, no payment block."""
    inner = plain_paragraphs_to_html(body_plain)
    return _email_wrapper(inner)
