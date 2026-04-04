<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-04 | Updated: 2026-04-04 -->

# buyer-research

## Purpose
Semi-independent sub-application for buyer research in M&A sell-side transactions. Analyzes target companies to identify and rank potential buyer groups. Deployed separately on Railway.

## Key Files

| File | Description |
|------|-------------|
| `CLAUDE.md` | AI agent context for this sub-app |
| `SETUP.md` | Setup and deployment instructions |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `backend/` | FastAPI buyer research API (see `backend/AGENTS.md`) |
| `frontend/` | Next.js frontend — scaffolded but not yet implemented |
| `.github/workflows/` | CI/CD — not yet configured |

## For AI Agents

### Working In This Directory
- This is a **separate deployable service** from the root Longlist app
- Has its own `requirements.txt`, `Procfile`, and `railway.toml` in `backend/`
- Frontend is empty scaffolding — don't try to build/run it yet
- Read `CLAUDE.md` and `SETUP.md` here for sub-app-specific context

### Testing Requirements
- Backend tests directory exists but is empty — tests need to be written
- Backend runs independently: `cd backend && uvicorn main:app --reload`

<!-- MANUAL: -->
