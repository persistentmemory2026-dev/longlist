"""Longlist — Excel generation with openpyxl, German formatting."""
import logging
import os
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger("longlist.excel")

# Styles
HEADER_FILL = PatternFill(start_color="B8D4E8", end_color="B8D4E8", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="1A1A1A")
CELL_FONT = Font(name="Calibri", size=10, color="333333")
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)

# Column definitions per package tier
BASE_COLUMNS = [
    ("Nr.", 5),
    ("Firma", 35),
    ("Rechtsform", 12),
    ("Handelsregister", 22),
    ("Adresse", 35),
    ("PLZ", 8),
    ("Stadt", 18),
    ("Geschäftsführer", 30),
    ("Website", 30),
    ("Telefon", 20),
]

FINANCIAL_COLUMNS = [
    ("Umsatz (EUR)", 16),
    ("Bilanzsumme (EUR)", 18),
    ("Eigenkapital (EUR)", 18),
    ("Mitarbeiter", 12),
    ("Geschäftsjahr", 14),
]

OWNER_COLUMNS = [
    ("Gesellschafter", 35),
    ("Beteiligung (%)", 15),
]

EMAIL_COLUMNS = [
    ("GF-Email", 30),
]


def _fmt_eur(value: Any) -> str:
    """Format a number as German EUR string (Punkt = Tausender)."""
    if value is None or value == "" or value == "n/v":
        return "n/v"
    try:
        num = float(value)
        # Convert from cents if value seems to be in cents (> 100000)
        if num > 100_000 and isinstance(value, (int, float)):
            num = num / 100
        if num == int(num):
            return f"{int(num):,}".replace(",", ".")
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)


def _safe(val: Any, default: str = "n/v") -> str:
    """Return val as string, or default if None/empty."""
    if val is None or val == "" or val == []:
        return default
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


def _extract_representatives(details: dict) -> str:
    """Extract Geschäftsführer names from details."""
    reps = details.get("representatives") or details.get("geschaeftsfuehrer") or []
    if isinstance(reps, list):
        names = []
        for r in reps:
            if isinstance(r, dict):
                name = r.get("name") or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                if name:
                    names.append(name)
            elif isinstance(r, str):
                names.append(r)
        return ", ".join(names) if names else "n/v"
    return _safe(reps)


def _extract_address(details: dict) -> tuple[str, str, str]:
    """Extract (street, zip, city) from details."""
    addr = details.get("address") or {}
    if isinstance(addr, dict):
        street = addr.get("street", "") or ""
        house = addr.get("house_number", "") or ""
        full_street = f"{street} {house}".strip() if street else "n/v"
        return full_street, _safe(addr.get("zip_code")), _safe(addr.get("city"))
    return "n/v", "n/v", "n/v"


def _extract_owners(owners_data: dict) -> list[tuple[str, str]]:
    """Extract list of (name, share%) from owners data."""
    owners_list = owners_data.get("owners") or owners_data.get("shareholders") or []
    if not isinstance(owners_list, list):
        return []
    results = []
    for o in owners_list:
        if isinstance(o, dict):
            name = o.get("name") or f"{o.get('first_name', '')} {o.get('last_name', '')}".strip()
            share = o.get("share_percent") or o.get("share") or ""
            results.append((name or "n/v", _safe(share)))
    return results


def generate_excel(
    companies: list[dict[str, Any]],
    package: str,
    job_id: str,
    output_dir: str = "/tmp",
) -> str:
    """
    Generate a formatted Excel file from enriched company data.

    Returns the file path.
    """
    includes_financials = package in ("standard", "premium")
    includes_owners = package == "premium"
    includes_email = package == "premium"

    # Build column list
    columns = list(BASE_COLUMNS)
    if includes_financials:
        columns.extend(FINANCIAL_COLUMNS)
    if includes_owners:
        columns.extend(OWNER_COLUMNS)
    if includes_email:
        columns.extend(EMAIL_COLUMNS)

    wb = Workbook()
    ws = wb.active
    ws.title = "Longlist"

    # Write header row
    for col_idx, (col_name, col_width) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    # Freeze header row
    ws.freeze_panes = "A2"

    # Write company rows
    for idx, company in enumerate(companies, 1):
        details = company.get("details", {})
        contact = company.get("contact", {})
        financials = company.get("financials", {})
        owners = company.get("owners", {})

        # Handle error responses
        if "error" in details:
            details = {}
        if "error" in contact:
            contact = {}
        if "error" in financials:
            financials = {}
        if "error" in owners:
            owners = {}

        street, plz, city = _extract_address(details)
        gf = _extract_representatives(details)

        row = idx + 1
        col = 1

        # Base columns
        values = [
            idx,  # Nr.
            _safe(details.get("name") or company.get("name")),
            _safe(details.get("legal_form")),
            _safe(details.get("register_number") or company.get("company_id")),
            street,
            plz,
            city,
            gf,
            _safe(contact.get("website") or details.get("website")),
            _safe(contact.get("phone") or details.get("phone")),
        ]

        if includes_financials:
            fin = financials.get("financials") or financials
            # Try to get most recent year
            annual = fin.get("annual_reports") or fin.get("reports") or []
            if isinstance(annual, list) and annual:
                latest = annual[0]  # Assume sorted descending
                values.extend([
                    _fmt_eur(latest.get("revenue")),
                    _fmt_eur(latest.get("balance_sheet_total")),
                    _fmt_eur(latest.get("equity")),
                    _safe(latest.get("employees")),
                    _safe(latest.get("fiscal_year") or latest.get("year")),
                ])
            else:
                values.extend([
                    _fmt_eur(fin.get("revenue")),
                    _fmt_eur(fin.get("balance_sheet_total")),
                    _fmt_eur(fin.get("equity")),
                    _safe(fin.get("employees")),
                    _safe(fin.get("fiscal_year")),
                ])

        if includes_owners:
            owner_list = _extract_owners(owners)
            if owner_list:
                values.append(", ".join(n for n, _ in owner_list))
                values.append(", ".join(s for _, s in owner_list))
            else:
                values.extend(["n/v", "n/v"])

        if includes_email:
            values.append(_safe(company.get("gf_email")))

        # Write values
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = CELL_FONT
            cell.border = THIN_BORDER
            if col_idx == 1:  # Nr. column centered
                cell.alignment = Alignment(horizontal="center")

    # Auto-filter
    if companies:
        last_col = get_column_letter(len(columns))
        last_row = len(companies) + 1
        ws.auto_filter.ref = f"A1:{last_col}{last_row}"

    # Save
    filename = f"Longlist_{job_id}_{package.upper()}.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    logger.info("Excel generated: %s (%d companies)", filepath, len(companies))

    return filepath
