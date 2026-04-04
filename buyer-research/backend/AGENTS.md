<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-04 | Updated: 2026-04-04 -->

# backend (buyer-research)

## Purpose
FastAPI backend for the buyer research service. Accepts a target company description, analyzes it with Claude AI, searches for matching buyer groups via OpenRegister, enriches results, and generates Excel reports.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI app entry point |
| `routes.py` | API route definitions |
| `config.py` | Environment configuration |
| `auth.py` | Authentication middleware |
| `db.py` | Database layer |
| `credits.py` | Credit/usage tracking for API consumers |
| `ai_client.py` | Claude API client for analysis |
| `analysis_service.py` | Core company analysis logic |
| `enrichment_service.py` | Data enrichment pipeline |
| `buyer_groups.py` | Buyer group matching and ranking |
| `target_analyzer.py` | Target company profile analysis |
| `openregister_client.py` | OpenRegister API client |
| `preview_search.py` | Company search preview |
| `excel_generator.py` | Excel report generation |
| `requirements.txt` | Python dependencies |
| `Procfile` | Railway deployment command |
| `railway.toml` | Railway service configuration |

## For AI Agents

### Working In This Directory
- This backend mirrors patterns from the root Longlist app but is independently deployable
- Uses the same OpenRegister API conventions (see root AGENTS.md for gotchas)
- German-language output for M&A advisor audience
- Credit-based access model for API consumers

### Testing Requirements
- Test directory exists at `tests/` but is empty — needs test coverage
- Run locally: `uvicorn main:app --reload`

### Common Patterns
- Route handlers in `routes.py`, business logic in service files
- AI analysis via `ai_client.py` → `analysis_service.py` → `buyer_groups.py`
- Enrichment flow: analyze target → match buyer groups → enrich via OpenRegister → generate Excel

## Dependencies

### Internal
- Shares architectural patterns with root Longlist app

### External
- `fastapi` + `uvicorn`
- `anthropic` — Claude AI
- `openregister-sdk` — Company data
- `openpyxl` — Excel generation

<!-- MANUAL: -->
