"""Longlist — Configuration & Environment Variables."""
import os
import logging

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local", override=True)

logger = logging.getLogger("longlist")

# --- Core APIs ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENREGISTER_API_KEY = os.getenv("OPENREGISTER_API_KEY", "")
ANYMAILFINDER_API_KEY = os.getenv("ANYMAILFINDER_API_KEY", "")

# --- Stripe ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# --- AgentMail ---
AGENTMAIL_API_KEY = os.getenv("AGENTMAIL_API_KEY", "")
AGENTMAIL_WEBHOOK_SECRET = os.getenv("AGENTMAIL_WEBHOOK_SECRET", "")
AGENTMAIL_FROM = os.getenv("AGENTMAIL_FROM", "briefing-mandatscout@agentmail.to")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- App ---
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
DATABASE_PATH = os.getenv("DATABASE_PATH", "longlist.db")
LONGLIST_ADMIN_TOKEN = os.getenv("LONGLIST_ADMIN_TOKEN", "")

# Stripe redirect URLs (defaults follow APP_URL; set STRIPE_SUCCESS_URL for longlist.email in prod)
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", f"{APP_URL}/danke")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", f"{APP_URL}/abgebrochen")

# --- Per-Company Dynamic Pricing (aligned with website longlist.email) ---
# Tier names match the website: Basis / Kontakt / Deep Data
# OpenRegister API credits: Details=10, Owners=10, Financials=10, UBOs=25, Holdings=10
PACKAGES = {
    "basis": {
        "label": "Basis",
        "endpoints": ["details"],                           # 10 credits
        "description": "Firmendaten + KI-Scoring",
        "description_long": "Firma, Rechtsform, HR-Nummer, Adresse, Geschäftsführer, Website, Telefon, Branche, KI-Scoring + Begründung",
        "stripe_product_name": "Longlist Basis — Firmendaten + Scoring",
        "stripe_description": (
            "Grundlegende Unternehmensdaten pro Firma: "
            "Firmenname, Rechtsform, Handelsregister-Nr., "
            "vollständige Adresse, Geschäftsführer, "
            "Website, Telefon, Branchencodes (WZ/NACE), "
            "KI-Relevanz-Scoring mit individueller Begründung. "
            "Lieferung als formatierte Excel-Datei innerhalb von 24h."
        ),
        "includes_financials": False,
        "includes_owners": False,
        "includes_ubos": False,
        "includes_holdings": False,
        "includes_email_lookup": False,
        "unit_price_eur_cents": 150,                        # 1,50 € per company
    },
    "kontakt": {
        "label": "Kontakt",
        "endpoints": ["details", "owners"],                 # 20 credits
        "description": "Firmendaten + GF-Kontakte + Gesellschafter",
        "description_long": "Alles aus Basis + GF-Kontaktdaten + Gesellschafterstruktur mit Beteiligungshöhe",
        "stripe_product_name": "Longlist Kontakt — Firmendaten + Kontakte",
        "stripe_description": (
            "Alle Daten aus Basis plus Kontaktdaten: "
            "Geschäftsführer-Kontakte, "
            "Gesellschafterstruktur mit Beteiligungshöhe. "
            "Ideal für die erste Direktansprache im M&A-Prozess. "
            "Lieferung als formatierte Excel-Datei innerhalb von 24h."
        ),
        "includes_financials": False,
        "includes_owners": True,
        "includes_ubos": False,
        "includes_holdings": False,
        "includes_email_lookup": False,
        "unit_price_eur_cents": 250,                        # 2,50 € per company
    },
    "deep_data": {
        "label": "Deep Data",
        "endpoints": ["details", "financials", "owners", "ubos", "holdings"],  # 65 credits
        "description": "Firmendaten + Kontakte + Finanzen + UBOs + Beteiligungen + GF-Email",
        "description_long": "Alles aus Kontakt + Finanzkennzahlen (Bundesanzeiger), wirtschaftlich Berechtigte (UBOs), Beteiligungen/Töchter, verifizierte GF-E-Mail",
        "stripe_product_name": "Longlist Deep Data — Vollständiges Firmenprofil",
        "stripe_description": (
            "Alle Daten aus Kontakt plus: "
            "detaillierte Finanzkennzahlen aus dem Bundesanzeiger, "
            "wirtschaftlich Berechtigte (UBOs) über alle Beteiligungsebenen, "
            "Tochtergesellschaften und Beteiligungen, "
            "verifizierte Geschäftsführer-E-Mail-Adresse. "
            "Das umfassendste Paket für M&A Due Diligence. "
            "Lieferung als formatierte Excel-Datei innerhalb von 24h."
        ),
        "includes_financials": True,
        "includes_owners": True,
        "includes_ubos": True,
        "includes_holdings": True,
        "includes_email_lookup": True,
        "unit_price_eur_cents": 400,                        # 4,00 € per company
    },
}

# --- Startup Warnings ---
_required = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "OPENREGISTER_API_KEY": OPENREGISTER_API_KEY,
}
_optional = {
    "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
    "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
    "AGENTMAIL_API_KEY": AGENTMAIL_API_KEY,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
}

for name, val in _required.items():
    if not val:
        logger.warning("REQUIRED env var %s is not set!", name)
for name, val in _optional.items():
    if not val:
        logger.info("Optional env var %s not set — feature will be skipped.", name)
