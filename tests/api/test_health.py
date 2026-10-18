import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add apps/api to path for testing
sys.path.append(os.path.join(os.path.dirname(__file__), '../../apps/api'))

from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_api_v1_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "API is healthy"
    assert "database" in data
    assert data["database"]["connected"] is True
