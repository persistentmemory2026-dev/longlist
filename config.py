"""Longlist — Configuration & Environment Variables."""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

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
AGENTMAIL_FROM = os.getenv("AGENTMAIL_FROM", "briefing@longlist.de")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- App ---
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
DATABASE_PATH = os.getenv("DATABASE_PATH", "longlist.db")
LONGLIST_ADMIN_TOKEN = os.getenv("LONGLIST_ADMIN_TOKEN", "")

# Stripe redirect URLs (defaults follow APP_URL; set STRIPE_SUCCESS_URL for longlist.de in prod)
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", f"{APP_URL}/danke")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", f"{APP_URL}/abgebrochen")

# --- Stripe Price IDs (live) ---
STRIPE_PRICES = {
    "enrichment": {
        "basis": os.getenv("STRIPE_PRICE_ENRICHMENT_BASIS", "price_1TEZBNAhhBDA1IxVv0iofGpG"),
        "standard": os.getenv("STRIPE_PRICE_ENRICHMENT_STANDARD", "price_1TEZBWAhhBDA1IxV529sW8Bf"),
        "premium": os.getenv("STRIPE_PRICE_ENRICHMENT_PREMIUM", "price_1TEZBdAhhBDA1IxVk4hFy662"),
    },
    "longlist": {
        "basis": os.getenv("STRIPE_PRICE_LONGLIST_BASIS", "price_1TEZBSAhhBDA1IxVHyb6TlKc"),
        "standard": os.getenv("STRIPE_PRICE_LONGLIST_STANDARD", "price_1TEZBZAhhBDA1IxVpPYQt5nP"),
        "premium": os.getenv("STRIPE_PRICE_LONGLIST_PREMIUM", "price_1TEZBhAhhBDA1IxVmt7ed7UW"),
    },
}

# --- Package Definitions ---
# Maps which OpenRegister endpoints to call per package tier
PACKAGES = {
    "basis": {
        "label": "BASIS",
        "endpoints": ["details", "contact"],
        "description": "Stammdaten, Adresse, GF, Website, Telefon",
        "includes_financials": False,
        "includes_owners": False,
        "includes_email_lookup": False,
    },
    "standard": {
        "label": "STANDARD",
        "endpoints": ["details", "contact", "financials"],
        "description": "Stammdaten + Umsatz, Bilanz, EK, Mitarbeiter",
        "includes_financials": True,
        "includes_owners": False,
        "includes_email_lookup": False,
    },
    "premium": {
        "label": "PREMIUM",
        "endpoints": ["details", "contact", "financials", "owners"],
        "description": "Stammdaten + Finanzen + Gesellschafter + GF-Email",
        "includes_financials": True,
        "includes_owners": True,
        "includes_email_lookup": True,
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
