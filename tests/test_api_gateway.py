import sys
import os

os.environ["TESTING"] = "true"
os.environ["MOCK_LLM"] = "true"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app

client = TestClient(app)


def test_root_status():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "system" in data
    assert "version" in data


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_chat_stream():
    response = client.post("/api/chat/stream", json={
        "message": "What is the current gold production at Shaft 2?",
        "session_id": "test_user",
        "interaction_mode": "web_chat"
    })
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
