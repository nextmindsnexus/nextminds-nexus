import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.api.app import app
from src.api.auth import get_current_user

# Mock auth
async def mock_get_current_user():
    return {"id": "123", "email": "test@example.com", "role": "admin"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

def test_health_endpoint():
    # Mocking db and embedder locally just for this test
    with patch("src.db.operations.get_connection") as mock_conn:
        with patch("src.embeddings.embedder.get_model") as mock_model:
            response = client.get("/api/admin/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]

def test_stats_endpoint():
    with patch("src.db.operations.get_activity_stats") as mock_stats:
        mock_stats.return_value = {
            "total": 100, "active": 90, "grade_bands": 4, "stages": 5,
            "oldest_crawl": "2023-01-01", "newest_crawl": "2023-12-01",
            "by_grade_band": {}, "by_stage": {}
        }
        response = client.get("/api/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["active"] == 90

@patch("src.ingest.run_full_ingestion")
@patch("src.summarizer.summarizer.run_summarization")
def test_ingest_combined_endpoint(mock_summarize, mock_ingestion):
    mock_ingestion.return_value = {"total_crawled": 50, "added": 10, "updated": 5, "removed": 0, "errors": 0}
    response = client.post("/api/admin/ingest")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["added"] == 10
    mock_ingestion.assert_called_once()
    mock_summarize.assert_called_once()

