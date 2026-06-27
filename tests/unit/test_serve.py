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
        assert "build_date" in body
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
        body = client.post(
            "/recommend",
            json={"customer_id": "abc123", "top_n": 5},
        ).json()
        assert "customer_id" in body
        assert "recommendations" in body
        assert "model_version" in body
        assert "source" in body
        for item in body["recommendations"]:
            assert "article_id" in item
            assert "score" in item

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
