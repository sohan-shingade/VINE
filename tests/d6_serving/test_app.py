"""HTTP contract tests for the D6 FastAPI app."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from vine.d6_serving import app as app_module


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_healthz_contract(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_irrigation_block_is_404(client):
    response = client.get("/irrigation/forecast", params={"block_id": "missing"})
    assert response.status_code == 404
    assert "unknown block" in response.json()["detail"]


def test_missing_snapshot_returns_generic_503_without_path(client, monkeypatch):
    missing_path = Path("/private/sensor-store/SE01-LS-1.parquet")
    missing_snapshot = Mock(
        side_effect=FileNotFoundError(2, "No such file or directory", missing_path)
    )
    warning = Mock()

    monkeypatch.setattr(app_module, "load_snapshot", missing_snapshot)
    monkeypatch.setattr(app_module.log, "warning", warning)
    response = client.get("/irrigation/forecast", params={"block_id": "Cc"})

    assert response.status_code == 503
    assert response.json() == {"detail": "irrigation forecast temporarily unavailable"}
    assert str(missing_path) not in response.text
    warning.assert_called_once()
    assert str(missing_path) in warning.call_args.kwargs["error"]
