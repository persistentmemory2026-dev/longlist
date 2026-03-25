"""Longlist — Tavily + Claude: Analyze a target company for sell-side mandates."""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY, TAVILY_API_KEY

logger = logging.getLogger("longlist.target_analyzer")

_ANALYSIS_SYSTEM = """Du bist ein erfahrener M&A-Analyst. Analysiere Zielunternehmen für Sell-Side-Mandate.
Antworte immer NUR mit einem JSON-Objekt, kein weiterer Text."""

_ANALYSIS_PROMPT = """Analysiere dieses Unternehmen für ein Sell-Side-Mandat (Käufersuche):

URL: {url}
Name: {name}

Website-Inhalt:
{website_content}

Zusätzliche Recherche:
{company_research}

Erstelle ein JSON-Objekt mit exakt dieser Struktur:
{{
  "name": "Firmenname GmbH",
  "url": "https://...",
  "industry": "Hauptbranche",
  "sub_industry": "Teilbranche / Spezialisierung",
  "products_services": ["Produkt/Service 1", "Produkt/Service 2"],
  "location": "Stadt, Bundesland",
  "size_estimate": "XX-XX Mitarbeiter",
  "revenue_estimate": "X-X Mio. EUR (Schätzung)",
  "market_position": "Kurzbeschreibung der Marktposition",
  "target_customers": ["Kundengruppe 1", "Kundengruppe 2"],
  "keywords": ["Keyword1", "Keyword2", "Keyword3"],
  "wz_codes": ["62", "63"],
  "summary": "2-3 Sätze Zusammenfassung des Unternehmens für M&A-Kontext"
}}

Schätze fehlende Informationen basierend auf Branche und verfügbaren Daten.
WZ-Codes müssen gültige deutsche Wirtschaftszweig-Klassifikationen sein (2-stellig)."""


async def analyze_target_company(
    url: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """
    Analyze a target company using Tavily (web scraping) + Claude (analysis).

    Returns structured company profile for buyer group definition.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    website_content = ""
    company_research = ""

    # Step 1: Tavily — scrape website + research
    if TAVILY_API_KEY:
        try:
            from tavily import AsyncTavilyClient

            tavily = AsyncTavilyClient(api_key=TAVILY_API_KEY)

            if url:
                extract_result = await tavily.extract(
                    urls=url,
                    extract_depth="advanced",
                )
                for r in extract_result.get("results", []):
                    website_content += r.get("raw_content", "")[:5000]

            search_query = f"Unternehmensprofil {name or url}"
            search_result = await tavily.search(
                query=search_query,
                search_depth="advanced",
                max_results=5,
            )
            for r in search_result.get("results", []):
                company_research += f"\n{r.get('content', '')}"
                if len(company_research) > 3000:
                    break

        except Exception as e:
            logger.warning("Tavily research failed: %s", e)
    else:
        logger.warning("TAVILY_API_KEY not set — skipping web research")

    # Step 2: Claude — analyze
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = _ANALYSIS_PROMPT.format(
        url=url or "nicht angegeben",
        name=name or "nicht angegeben",
        website_content=website_content[:5000] if website_content else "(keine Website-Daten verfügbar)",
        company_research=company_research[:3000] if company_research else "(keine Recherche-Daten)",
    )

    logger.info("Analyzing target company: %s / %s", name, url)

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=_ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    try:
        analysis = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse target analysis: %s\nRaw: %s", e, raw_text[:500])
        raise ValueError(f"Target analysis returned invalid JSON: {e}") from e

    # Ensure defaults
    analysis.setdefault("name", name or "")
    analysis.setdefault("url", url or "")
    analysis.setdefault("industry", "")
    analysis.setdefault("keywords", [])
    analysis.setdefault("wz_codes", [])
    analysis.setdefault("summary", "")

    logger.info("Target analysis complete: %s (%s)", analysis["name"], analysis.get("industry"))
    return analysis
