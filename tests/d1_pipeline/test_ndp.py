"""NDP client tests — construction + action plumbing (no network)."""

from vine.d1_pipeline.ndp import NDPClient


def test_base_url_trailing_slash_stripped():
    c = NDPClient(base_url="https://example.org/")
    assert c.base_url == "https://example.org"


def test_api_key_sets_auth_header():
    c = NDPClient(base_url="https://example.org", api_key="tok123")
    assert c._session.headers["Authorization"] == "tok123"


def test_no_api_key_means_no_auth_header():
    c = NDPClient(base_url="https://example.org", api_key="")
    assert "Authorization" not in c._session.headers


def test_action_parses_ckan_envelope(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True, "result": {"results": [{"name": "ds1"}]}}

    c = NDPClient(base_url="https://example.org")
    monkeypatch.setattr(c._session, "get", lambda *a, **k: FakeResp())
    assert c.search("vineyard") == [{"name": "ds1"}]
