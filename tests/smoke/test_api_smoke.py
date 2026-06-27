"""
API smoke test — confirms the running service is reachable and healthy.

This test is designed to run against a live server (via Docker or Cloud Run).
Set SMOKE_BASE_URL environment variable to point at the target environment.

Default (CI without a running server): uses FastAPI TestClient.
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.serve.app import app

BASE_URL = os.getenv("SMOKE_BASE_URL", "")  # empty → use TestClient

# Use TestClient when no external URL is configured (CI default)
_client = TestClient(app) if not BASE_URL else None


def get(path: str):
    if _client:
        return _client.get(path)
    import httpx  # noqa: PLC0415

    return httpx.get(f"{BASE_URL}{path}", timeout=10)


def post(path: str, **kwargs):
    if _client:
        return _client.post(path, **kwargs)
    import httpx  # noqa: PLC0415

    return httpx.post(f"{BASE_URL}{path}", timeout=10, **kwargs)


@pytest.mark.smoke
class TestApiSmoke:
    def test_health_is_alive(self):
        """Service must respond 200 on /health within timeout."""
        r = get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"

    def test_version_is_reachable(self):
        r = get("/version")
        assert r.status_code == 200

    def test_recommend_returns_results(self):
        r = post("/recommend", json={"customer_id": "smoke-test-user", "top_n": 5})
        assert r.status_code == 200
        body = r.json()
        assert len(body["recommendations"]) > 0, "Recommend endpoint returned empty list"
