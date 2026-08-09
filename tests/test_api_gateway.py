import sys
import os
import hmac
import hashlib

os.environ["TESTING"] = "true"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token"
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


def test_whatsapp_webhook_verification():
    response = client.get("/webhook?hub.mode=subscribe&hub.challenge=test_challenge&hub.verify_token=test_verify_token")
    assert response.status_code == 200
    assert response.text == '"test_challenge"'


def test_whatsapp_webhook_verification_mismatch():
    response = client.get("/webhook?hub.mode=subscribe&hub.challenge=test_challenge&hub.verify_token=wrong_token")
    assert response.status_code == 403


def test_receive_text_message():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123456", "phone_number_id": "789"},
                            "contacts": [{"profile": {"name": "Test User"}, "wa_id": "27820000000"}],
                            "messages": [
                                {
                                    "from": "27820000000",
                                    "id": "ABGGFlKwvUFPAhALeq8p73H",
                                    "timestamp": "1720743600",
                                    "text": {"body": "What is the current gold production at Shaft 2?"},
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    import json
    body_bytes = json.dumps(payload).encode()
    signature = hmac.new(os.environ["SECRET_KEY"].encode(), body_bytes, hashlib.sha256).hexdigest()
    response = client.post("/webhook", content=body_bytes, headers={"X-Hub-Signature-256": f"sha256={signature}", "Content-Type": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "text" in data["response"]
