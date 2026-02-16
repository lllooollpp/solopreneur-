import pytest
from fastapi.testclient import TestClient
from main import app
from concurrent.futures import ThreadPoolExecutor

def test_concurrent_registrations_same_email():
    client = TestClient(app)
    
    def register_user():
        return client.post("/api/register", json={"email": "same@example.com", "password": "123456"})
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(register_user) for _ in range(5)]
        results = [f.result() for f in futures]
    
    # 第一个注册应该成功，其余应失败
    success_count = sum(1 for r in results if r.status_code == 201)
    error_count = sum(1 for r in results if r.status_code == 400)
    assert success_count == 1
    assert error_count == 4

def test_concurrent_registrations_unique_emails():
    client = TestClient(app)
    
    def register_user(email):
        return client.post("/api/register", json={"email": email, "password": "123456"})
    
    emails = [f"user{i}@example.com" for i in range(5)]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(register_user, email) for email in emails]
        results = [f.result() for f in futures]
    
    for response in results:
        assert response.status_code == 201
        assert response.json()["email"] == emails[results.index(response)]