import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login_empty_credentials():
    response = client.post("/api/login", json={"username": "", "password": ""})
    assert response.status_code == 400
    assert "Missing credentials" in response.json()["detail"]

def test_login_invalid_username():
    response = client.post("/api/login", json={"username": "invalid_user", "password": "valid_pass"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]

def test_login_password_length():
    response = client.post("/api/login", json={"username": "valid_user", "password": "123"})
    assert response.status_code == 400
    assert "Password must be at least 6 characters" in response.json()["detail"]