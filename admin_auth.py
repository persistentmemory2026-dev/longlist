"""Optional Bearer token for operator-only HTTP routes."""
from __future__ import annotations

from fastapi import Header, HTTPException


def require_admin(authorization: str | None = Header(None)) -> None:
    from config import LONGLIST_ADMIN_TOKEN

    if not LONGLIST_ADMIN_TOKEN:
        return
    expected = f"Bearer {LONGLIST_ADMIN_TOKEN}"
    if (authorization or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
