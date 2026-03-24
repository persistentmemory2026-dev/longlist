def test_verify_webhook_returns_none_without_secret(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    import importlib

    import config

    importlib.reload(config)
    import stripe_handler

    importlib.reload(stripe_handler)
    assert stripe_handler.verify_webhook(b"{}", "sig") is None
