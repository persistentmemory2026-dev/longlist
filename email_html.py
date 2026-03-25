"""Convert plaintext email bodies to safe HTML and build Stripe Checkout CTA blocks."""
from __future__ import annotations

import html
import re

from config import PACKAGES

# Stripe brand purple (approximation for email CTAs)
_STRIPE_BUTTON_BG = "#635BFF"
_STRIPE_BUTTON_COLOR = "#ffffff"

_PACKAGE_ORDER = ("basis", "standard", "premium")


def _fmt_eur(cents: int) -> str:
    """Format EUR cents as German price (e.g. 150 → '1,50 €')."""
    eur = cents / 100
    if eur == int(eur):
        return f"{int(eur)},00 €"
    return f"{eur:.2f} €".replace(".", ",")


def plain_paragraphs_to_html(text: str) -> str:
    """
    Split on blank lines into paragraphs; each paragraph becomes <p>.
    Single newlines inside a paragraph become <br>.
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
        inner = html.escape(chunk).replace("\n", "<br>\n")
        blocks.append(
            '<p style="margin:0 0 14px 0;font-family:Helvetica,Arial,sans-serif;'
            f'font-size:15px;line-height:1.55;color:#1f1f1f;">{inner}</p>'
        )
    return "\n".join(blocks)


def build_checkout_cta_plaintext(urls: dict[str, str], total_companies: int = 0) -> str:
    """Appendix for multipart/alternative text part — URLs must match HTML CTAs."""
    lines = [
        "",
        "Zahlung — bitte wählen Sie Ihr Paket:",
        "",
    ]
    for key in _PACKAGE_ORDER:
        pkg = PACKAGES[key]
        label = pkg["label"]
        url = urls.get(key, "#")
        if total_companies > 0:
            total = _fmt_eur(pkg["unit_price_eur_cents"] * total_companies)
            lines.append(f"{label} ({total}): {url}")
        else:
            lines.append(f"{label}: {url}")
    return "\n".join(lines)


def _bulletproof_button_row(url: str, button_label: str, package_line: str) -> str:
    safe_href = html.escape(url, quote=True)

    btn = html.escape(button_label)
    line = html.escape(package_line)

    return f"""<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom:20px;">
  <tr>
    <td style="font-family:Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;color:#1f1f1f;">
      <p style="margin:0 0 8px 0;">{line}</p>
      <table role="presentation" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td style="border-radius:6px;background-color:{_STRIPE_BUTTON_BG};">
            <a href="{safe_href}" target="_blank" rel="noopener noreferrer"
               style="display:inline-block;padding:12px 22px;font-family:Helvetica,Arial,sans-serif;
                      font-size:14px;font-weight:600;color:{_STRIPE_BUTTON_COLOR};text-decoration:none;">
              {btn}
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def build_checkout_cta_block(urls: dict[str, str], total_companies: int = 0) -> str:
    """Bulletproof table-based buttons linking to Stripe Checkout (one per package)."""
    rows: list[str] = [
        '<div style="margin-top:8px;">',
        '<p style="margin:0 0 16px 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;'
        'font-weight:600;color:#1f1f1f;">Zahlung abschließen</p>',
    ]
    for key in _PACKAGE_ORDER:
        meta = PACKAGES[key]
        label = meta["label"]
        desc = meta["description"]
        url = urls.get(key) or "#"

        if total_companies > 0:
            unit = _fmt_eur(meta["unit_price_eur_cents"])
            total = _fmt_eur(meta["unit_price_eur_cents"] * total_companies)
            package_line = f"{label} — {desc} ({unit}/Unternehmen × {total_companies} = {total})"
            button_label = f"{label} bezahlen — {total}"
        else:
            package_line = f"{label} — {desc}"
            button_label = f"Mit {label} bezahlen"

        rows.append(_bulletproof_button_row(url, button_label, package_line))
    rows.append("</div>")
    return "\n".join(rows)


def build_preview_email_html(body_plain: str, payment_urls: dict[str, str], total_companies: int = 0) -> str:
    """Full HTML for the offer email: prose + checkout CTAs."""
    prose = plain_paragraphs_to_html(body_plain)
    cta = build_checkout_cta_block(payment_urls, total_companies)
    return f'{prose}\n{cta}'


def build_delivery_email_html(body_plain: str) -> str:
    """HTML for delivery email — paragraphs only, no payment block."""
    return plain_paragraphs_to_html(body_plain)
