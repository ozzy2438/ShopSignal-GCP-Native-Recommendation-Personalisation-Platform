"""Unit tests for the FastAPI application (no real server needed)."""

from fastapi.testclient import TestClient

from src.serve.app import APP_VERSION, app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body(self):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert "env" in body


class TestVersionEndpoint:
    def test_version_returns_200(self):
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_body(self):
        body = client.get("/version").json()
        assert body["version"] == APP_VERSION
        assert "env" in body
        assert "model_stage" in body


class TestRecommendEndpoint:
    def test_recommend_returns_200(self):
        response = client.post(
            "/recommend",
            json={"customer_id": "00000dbacae5abe5e23885899a1fa44253a17956", "top_n": 5},
        )
        assert response.status_code == 200

    def test_recommend_returns_correct_count(self):
        body = client.post(
            "/recommend",
            json={"customer_id": "abc123", "top_n": 3},
        ).json()
        assert len(body["recommendations"]) == 3

    def test_recommend_response_schema(self):
        top_n = 5
        body = client.post(
            "/recommend",
            json={"customer_id": "abc123", "top_n": top_n},
        ).json()
        assert body["customer_id"] == "abc123"
        assert body["model_version"] == APP_VERSION
        assert body["source"] == "mock"
        recs = body["recommendations"]
        assert len(recs) == min(top_n, 10)
        for item in recs:
            assert "article_id" in item
            assert "score" in item
        scores = [item["score"] for item in recs]
        assert scores == sorted(scores, reverse=True), (
            "recommendations should be ordered by score descending"
        )

    def test_recommend_empty_customer_id_returns_422(self):
        response = client.post("/recommend", json={"customer_id": "", "top_n": 5})
        assert response.status_code == 422

    def test_recommend_top_n_capped_at_10(self):
        """Mock implementation caps results at 10 regardless of top_n."""
        body = client.post(
            "/recommend",
            json={"customer_id": "abc", "top_n": 50},
        ).json()
        assert len(body["recommendations"]) <= 10

    # ── top_n boundary validation ─────────────────────────────────────────────

    def test_recommend_top_n_zero_returns_422(self):
        response = client.post("/recommend", json={"customer_id": "abc", "top_n": 0})
        assert response.status_code == 422

    def test_recommend_top_n_above_max_returns_422(self):
        response = client.post("/recommend", json={"customer_id": "abc", "top_n": 51})
        assert response.status_code == 422

    def test_recommend_top_n_min_boundary_returns_200(self):
        response = client.post("/recommend", json={"customer_id": "abc", "top_n": 1})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) == 1

    def test_recommend_top_n_max_boundary_returns_200(self):
        response = client.post("/recommend", json={"customer_id": "abc", "top_n": 50})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) <= 10
