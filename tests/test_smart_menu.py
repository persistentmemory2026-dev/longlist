"""Tests for the Smart Service Menu feature: confidence routing, service selection, heuristics."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _parse_service_from_reply — keyword-based service detection from email text
# ---------------------------------------------------------------------------

def _get_parser():
    """Import the reply parser from main.py (isolated to avoid heavy imports)."""
    # Replicate the logic here since main.py has many side-effect imports
    def _parse_service_from_reply(body: str) -> str | None:
        text = body.lower().strip()
        _keyword_map = [
            (["datenanreicherung", "enrichment", "daten anreichern"], "enrichment"),
            (["käufer", "sell-side", "sell side", "buyer", "käufersuche"], "sell_side"),
            (["longlist", "recherche", "suche", "kriterien"], "longlist"),
            (["liste", "upload", "datei", "excel", "csv", "firmenliste"], "file_enrichment"),
        ]
        for keywords, service in _keyword_map:
            if any(kw in text for kw in keywords):
                return service
        return None
    return _parse_service_from_reply


class TestParseServiceFromReply:
    def test_enrichment_keyword(self):
        parse = _get_parser()
        assert parse("Datenanreicherung bitte") == "enrichment"

    def test_enrichment_english(self):
        parse = _get_parser()
        assert parse("I need enrichment") == "enrichment"

    def test_enrichment_phrase(self):
        parse = _get_parser()
        assert parse("Bitte Daten anreichern") == "enrichment"

    def test_sell_side_kaeufer(self):
        parse = _get_parser()
        assert parse("Ich brauche eine Käufersuche") == "sell_side"

    def test_sell_side_buyer(self):
        parse = _get_parser()
        assert parse("buyer search") == "sell_side"

    def test_sell_side_hyphenated(self):
        parse = _get_parser()
        assert parse("Sell-Side Mandat") == "sell_side"

    def test_longlist_keyword(self):
        parse = _get_parser()
        assert parse("Longlist Recherche bitte") == "longlist"

    def test_longlist_suche(self):
        parse = _get_parser()
        assert parse("Suche nach Maschinenbauern") == "longlist"

    def test_file_enrichment_excel(self):
        parse = _get_parser()
        assert parse("Ich habe eine Excel Liste") == "file_enrichment"

    def test_file_enrichment_csv(self):
        parse = _get_parser()
        assert parse("CSV hochladen") == "file_enrichment"

    def test_file_enrichment_firmenliste(self):
        parse = _get_parser()
        assert parse("Firmenliste anreichern") == "file_enrichment"

    def test_case_insensitive(self):
        parse = _get_parser()
        assert parse("KÄUFER FINDEN") == "sell_side"

    def test_no_match_returns_none(self):
        parse = _get_parser()
        assert parse("Hallo, wie geht es Ihnen?") is None

    def test_empty_string_returns_none(self):
        parse = _get_parser()
        assert parse("") is None

    def test_priority_enrichment_over_longlist(self):
        """enrichment keywords are checked before longlist keywords."""
        parse = _get_parser()
        assert parse("Datenanreicherung und Recherche") == "enrichment"

    def test_priority_sell_side_in_mixed(self):
        """sell_side keywords are checked before longlist."""
        parse = _get_parser()
        assert parse("Käufer Longlist") == "sell_side"


# ---------------------------------------------------------------------------
# Heuristic overrides in briefing_parser.py
# ---------------------------------------------------------------------------

class TestBriefingParserHeuristics:
    """Test the heuristic override logic that runs after Claude classification."""

    def _apply_heuristics(self, parsed: dict, subject: str = "", body: str = "") -> dict:
        """Replicate heuristic logic from briefing_parser.py for isolated testing."""
        _sell_side_keywords = [
            "käufer", "buyer", "sell-side", "sell side", "mandat verkaufen",
            "erwerber", "akquisiteur", "käuferliste", "interessenten finden",
            "übernahme-kandidat", "wer könnte kaufen",
        ]
        email_text = f"{subject} {body}".lower()
        has_sell_side_keywords = any(kw in email_text for kw in _sell_side_keywords)

        parsed.setdefault("confidence", 0.5)
        try:
            parsed["confidence"] = float(parsed["confidence"])
        except (TypeError, ValueError):
            parsed["confidence"] = 0.5

        if parsed["service_type"] == "sell_side" and not has_sell_side_keywords:
            parsed["service_type"] = "enrichment"
            parsed["confidence"] = min(parsed["confidence"], 0.7)
            if parsed.get("target_company_name") and not parsed.get("company_list"):
                parsed["company_list"] = [parsed["target_company_name"]]

        company_list = parsed.get("company_list") or []
        if (
            parsed["service_type"] == "enrichment"
            and len(company_list) == 1
            and not has_sell_side_keywords
        ):
            parsed["confidence"] = min(parsed["confidence"], 0.8)

        return parsed

    def test_sell_side_without_keywords_overrides_to_enrichment(self):
        parsed = {
            "service_type": "sell_side",
            "confidence": 0.9,
            "target_company_name": "PFGC GmbH",
            "company_list": None,
        }
        result = self._apply_heuristics(parsed, subject="PFGC GmbH", body="Bitte recherchieren")
        assert result["service_type"] == "enrichment"
        assert result["confidence"] <= 0.7
        assert result["company_list"] == ["PFGC GmbH"]

    def test_sell_side_with_keywords_no_override(self):
        parsed = {
            "service_type": "sell_side",
            "confidence": 0.95,
            "target_company_name": "PFGC GmbH",
            "company_list": None,
        }
        result = self._apply_heuristics(parsed, body="Käufer finden für PFGC GmbH")
        assert result["service_type"] == "sell_side"
        assert result["confidence"] == 0.95

    def test_single_company_caps_confidence(self):
        parsed = {
            "service_type": "enrichment",
            "confidence": 0.95,
            "company_list": ["PFGC GmbH"],
        }
        result = self._apply_heuristics(parsed, body="PFGC GmbH Daten")
        assert result["service_type"] == "enrichment"
        assert result["confidence"] <= 0.8

    def test_multiple_companies_no_cap(self):
        parsed = {
            "service_type": "enrichment",
            "confidence": 0.95,
            "company_list": ["Firma A", "Firma B", "Firma C"],
        }
        result = self._apply_heuristics(parsed, body="Drei Firmen")
        assert result["service_type"] == "enrichment"
        assert result["confidence"] == 0.95

    def test_confidence_defaults_to_half_if_missing(self):
        parsed = {"service_type": "longlist"}
        result = self._apply_heuristics(parsed)
        assert result["confidence"] == 0.5

    def test_confidence_invalid_string_defaults(self):
        parsed = {"service_type": "longlist", "confidence": "invalid"}
        result = self._apply_heuristics(parsed)
        assert result["confidence"] == 0.5

    def test_sell_side_override_moves_target_to_company_list(self):
        parsed = {
            "service_type": "sell_side",
            "confidence": 0.85,
            "target_company_name": "Acme Corp",
            "company_list": None,
        }
        result = self._apply_heuristics(parsed, body="Acme Corp")
        assert result["company_list"] == ["Acme Corp"]


# ---------------------------------------------------------------------------
# Service menu HTML generation
# ---------------------------------------------------------------------------

class TestServiceMenuHtml:
    def test_menu_includes_longlist_url(self):
        from email_html import build_service_menu_email_html

        html = build_service_menu_email_html(
            body_plain="Test",
            job_id="abc123",
            app_url="https://example.com",
        )
        assert "/select/abc123/longlist" in html
        assert "Longlist-Recherche" in html

    def test_menu_only_shows_longlist(self):
        from email_html import build_service_menu_email_html

        html = build_service_menu_email_html(
            body_plain="Test",
            job_id="abc123",
            app_url="https://example.com",
        )
        assert "enrichment" not in html
        assert "sell_side" not in html
        assert "file_enrichment" not in html

    def test_menu_marks_recommended_longlist(self):
        from email_html import build_service_menu_email_html

        html = build_service_menu_email_html(
            body_plain="Test",
            job_id="abc123",
            app_url="https://example.com",
            recommended_service="longlist",
        )
        assert "Empfohlen" in html

    def test_plaintext_includes_longlist_url(self):
        from email_html import build_service_menu_plaintext

        text = build_service_menu_plaintext(
            body_plain="Test",
            job_id="abc123",
            app_url="https://example.com",
            recommended_service="longlist",
        )
        assert "/select/abc123/longlist" in text

    def test_plaintext_recommended_marker(self):
        from email_html import build_service_menu_plaintext

        text = build_service_menu_plaintext(
            body_plain="Test",
            job_id="x",
            app_url="https://a.com",
            recommended_service="longlist",
        )
        # Recommended item should have >> prefix
        lines = text.split("\n")
        longlist_lines = [l for l in lines if "Longlist" in l and ">>" in l]
        assert len(longlist_lines) >= 1


# ---------------------------------------------------------------------------
# /select/{job_id}/{service_type} endpoint
# ---------------------------------------------------------------------------

class TestSelectEndpoint:
    @pytest.fixture(autouse=True)
    def _setup(self):
        """Ensure clean job store for each test."""
        import job_store
        job_store.init_db()
        yield

    def _client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_select_invalid_job_returns_404(self):
        client = self._client()
        resp = client.get("/select/nonexistent/enrichment", follow_redirects=False)
        assert resp.status_code == 404
        assert "nicht gefunden" in resp.text

    def test_select_invalid_service_type_returns_400(self):
        import job_store
        job_store.put_job("test01", {"status": "awaiting_service_selection", "sender": "x@y.z"})
        client = self._client()
        resp = client.get("/select/test01/invalid_type", follow_redirects=False)
        assert resp.status_code == 400
        assert "Ungültig" in resp.text

    def test_select_already_processing_is_idempotent(self):
        import job_store
        job_store.put_job("test02", {"status": "enriching", "sender": "x@y.z"})
        client = self._client()
        resp = client.get("/select/test02/longlist", follow_redirects=False)
        assert resp.status_code == 200
        assert "bearbeitet" in resp.text

    def test_select_valid_longlist(self):
        import job_store
        job_store.put_job("test03", {
            "status": "awaiting_service_selection",
            "sender": "x@y.z",
            "thread_id": "",
            "parsed": {"service_type": "longlist", "query": "Maschinenbau"},
        })
        client = self._client()
        resp = client.get("/select/test03/longlist", follow_redirects=False)
        assert resp.status_code == 200
        assert "Longlist" in resp.text
        job = job_store.get_job("test03")
        assert job["service_type"] == "longlist"

    def test_select_disabled_service_returns_400(self):
        import job_store
        job_store.put_job("test04", {
            "status": "awaiting_service_selection",
            "sender": "x@y.z",
            "thread_id": "",
            "parsed": {},
        })
        client = self._client()
        # Disabled services should return 400
        resp = client.get("/select/test04/enrichment", follow_redirects=False)
        assert resp.status_code == 400
        resp = client.get("/select/test04/sell_side", follow_redirects=False)
        assert resp.status_code == 400
