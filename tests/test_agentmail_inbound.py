import json

from agentmail_inbound import (
    extract_inbound_email_fields,
    verify_and_parse_agentmail_body,
)


def test_extract_inbound_email_fields():
    payload = {
        "message": {
            "from": {"email": "client@example.com"},
            "subject": "Longlist",
            "text": "Body text",
            "thread_id": "th_123",
        }
    }
    assert extract_inbound_email_fields(payload) == (
        "client@example.com",
        "Longlist",
        "Body text",
        "th_123",
    )


def test_verify_skips_signature_when_secret_unset(monkeypatch):
    monkeypatch.delenv("AGENTMAIL_WEBHOOK_SECRET", raising=False)
    import importlib

    import config

    importlib.reload(config)
    raw = json.dumps({"message": {"from": {"email": "x@y.z"}, "subject": "S"}}).encode()
    from agentmail_inbound import verify_and_parse_agentmail_body

    payload, err = verify_and_parse_agentmail_body(raw, {})
    assert err is None
    assert "message" in payload


def test_normalize_ignores_non_message_events():
    from agentmail_inbound import _normalize_svix_payload

    p = _normalize_svix_payload({"event_type": "domain.verified", "data": {}})
    assert p.get("_longlist_ignore_event") is True
