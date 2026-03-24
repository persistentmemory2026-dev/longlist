import pytest
from fastapi import HTTPException


def test_require_admin_allows_when_token_unset(monkeypatch):
    monkeypatch.delenv("LONGLIST_ADMIN_TOKEN", raising=False)
    import importlib

    import config

    importlib.reload(config)
    from admin_auth import require_admin

    require_admin(None)


def test_require_admin_enforces_bearer(monkeypatch):
    monkeypatch.setenv("LONGLIST_ADMIN_TOKEN", "good")
    import importlib

    import config

    importlib.reload(config)
    from admin_auth import require_admin

    with pytest.raises(HTTPException) as ei:
        require_admin("Bearer bad")
    assert ei.value.status_code == 401
    require_admin("Bearer good")
