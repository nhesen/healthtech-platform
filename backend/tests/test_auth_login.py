import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app, DB_PATH


def reset():
    if DB_PATH.exists(): DB_PATH.unlink()
    from app.main import seed
    seed()


CREDENTIALS = [("1AZ0001", "PATIENT", "patient@demo.az"), ("2AZ0002", "DOCTOR", "doctor@demo.az"), ("3AZ0003", "HOSPITAL_ADMIN", "admin@demo.az")]


def test_login_returns_demo_identity_for_every_role():
    reset(); c = TestClient(app)
    for fin, role, email in CREDENTIALS:
        response = c.post("/auth/login", json={"fin": fin, "role": role})
        assert response.status_code == 200, (fin, role, response.text)
        body = response.json()
        assert body["email"] == email and body["role"] == role and body["id"] and body["name"]


def test_login_accepts_lowercase_fin():
    reset(); c = TestClient(app)
    assert c.post("/auth/login", json={"fin": "1az0001", "role": "PATIENT"}).json()["email"] == "patient@demo.az"


def test_login_rejects_role_that_does_not_match_the_fin():
    reset(); c = TestClient(app)
    assert c.post("/auth/login", json={"fin": "1AZ0001", "role": "DOCTOR"}).status_code == 401
    assert c.post("/auth/login", json={"fin": "3AZ0003", "role": "PATIENT"}).status_code == 401


def test_login_rejects_unknown_fin():
    reset(); c = TestClient(app)
    assert c.post("/auth/login", json={"fin": "9ZZ9999", "role": "PATIENT"}).status_code == 401


def test_login_validates_fin_format():
    reset(); c = TestClient(app)
    for value in ["12", "1AZ00012", "1AZ 001", "1AZ-001"]:
        assert c.post("/auth/login", json={"fin": value, "role": "PATIENT"}).status_code == 422
    assert c.post("/auth/login", json={"fin": "1AZ0001", "role": "MAYOR"}).status_code == 422


def test_login_never_echoes_the_submitted_fin():
    reset(); c = TestClient(app)
    body = c.post("/auth/login", json={"fin": "1AZ0001", "role": "PATIENT"}).text
    assert "1AZ0001" not in body
    assert "1AZ0001" not in c.post("/auth/login", json={"fin": "1AZ0001", "role": "DOCTOR"}).text


def test_login_session_email_authorises_protected_endpoints():
    reset(); c = TestClient(app)
    doctor = c.post("/auth/login", json={"fin": "2AZ0002", "role": "DOCTOR"}).json()["email"]
    assert c.get("/appointments", headers={"X-Demo-User": doctor}).status_code == 200
    assert c.get("/auth/me", headers={"X-Demo-User": doctor}).json()["role"] == "DOCTOR"
    admin = c.post("/auth/login", json={"fin": "3AZ0003", "role": "HOSPITAL_ADMIN"}).json()["email"]
    assert c.get("/tasks", headers={"X-Demo-User": admin}).status_code == 200
    assert c.get("/tasks", headers={"X-Demo-User": doctor}).status_code == 403


def test_login_is_unavailable_when_demo_mode_is_disabled(monkeypatch):
    reset(); c = TestClient(app)
    monkeypatch.setenv("DEMO_MODE", "false")
    assert c.post("/auth/login", json={"fin": "1AZ0001", "role": "PATIENT"}).status_code == 404


def test_demo_reset_does_not_invalidate_a_logged_in_session():
    reset(); c = TestClient(app)
    admin = c.post("/auth/login", json={"fin": "3AZ0003", "role": "HOSPITAL_ADMIN"}).json()["email"]
    assert c.post("/demo/reset", headers={"X-Demo-User": admin}).status_code == 200
    assert c.get("/auth/me", headers={"X-Demo-User": admin}).status_code == 200
