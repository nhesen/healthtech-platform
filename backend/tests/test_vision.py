"""Hospital vision upload and YOLO Pose occupancy events."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import DB_PATH, app

ADMIN = {"X-Demo-User": "admin@demo.az"}
PATIENT = {"X-Demo-User": "patient@demo.az"}
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def reset():
    if DB_PATH.exists():
        DB_PATH.unlink()
    from app.main import seed
    seed()


def test_vision_status_never_claims_identity_recognition():
    reset()
    body = TestClient(app).get("/cv/vision-status", headers=ADMIN).json()
    assert body["identity_recognition"] is False
    assert body["frames_sent_to_api"] is False
    assert "yolo_active" in body
    assert TestClient(app).get("/cv/vision-status", headers=PATIENT).status_code == 403


def test_analyze_rejects_non_admin_and_non_media():
    reset()
    c = TestClient(app)
    assert c.post("/cv/analyze", headers=PATIENT, files={"file": ("a.jpg", JPEG, "image/jpeg")}).status_code == 403
    assert c.post("/cv/analyze", headers=ADMIN, files={"file": ("note.txt", b"hello", "text/plain")}).status_code == 422


def test_analyze_is_honest_when_yolo_is_inactive(monkeypatch):
    reset()
    from app import vision
    monkeypatch.setattr(vision, "yolo_available", lambda: False)
    def fail(*_args, **_kwargs):
        from fastapi import HTTPException
        raise HTTPException(503, "Install cv_service/requirements-vision.txt and retry.")
    monkeypatch.setattr("app.main.run_pose_analysis", fail)
    response = TestClient(app).post("/cv/analyze", headers=ADMIN, files={"file": ("scene.jpg", JPEG, "image/jpeg")})
    assert response.status_code == 503
    assert "YOLO" in response.json()["detail"] or "vision" in response.json()["detail"].lower() or "Install" in response.json()["detail"]


def _yolo_payload(**overrides):
    payload = {
        "yolo_active": True,
        "engine": "ultralytics-yolo-pose",
        "identity_recognition": False,
        "frames_discarded": True,
        "frames_analyzed": 4,
        "peak_people": 9,
        "average_people": 8.25,
        "empty_seats": 3,
        "seats_detected": 12,
        "latest_people": [{"index": 0, "state": "STANDING", "confidence": 0.9}],
        "crowding": {
            "level": "OVERCROWDED",
            "peak_people": 9,
            "average_people": 8.25,
            "explanation": "YOLO Pose counted a peak of 9 people.",
        },
        "movement": {
            "pose_counts": {"STANDING": 9},
            "transitions": ["SITTING->STANDING"],
            "incoming_people": True,
            "fall_risk_signal": True,
            "explanation": "Pose transitions were observed.",
        },
    }
    payload.update(overrides)
    return payload


def test_analyze_overcrowding_posts_event_without_fall_risk_room(monkeypatch):
    reset()
    monkeypatch.setattr("app.main.run_pose_analysis", lambda *_args, **_kwargs: _yolo_payload(movement={
        "pose_counts": {"STANDING": 9},
        "transitions": [],
        "incoming_people": True,
        "fall_risk_signal": False,
        "explanation": "No stable pose transition was observed in the sampled frames.",
    }))
    c = TestClient(app)
    body = c.post("/cv/analyze", headers=ADMIN, files={"file": ("scene.jpg", JPEG, "image/jpeg")}, data={"room_id": "204"}).json()
    assert body["yolo_active"] is True
    assert body["crowding"]["level"] == "OVERCROWDED"
    assert body["events_posted"]
    checks = c.get("/health/demo", headers=ADMIN).json()["checks"]
    assert checks["room_204_stable"] is True
    events = c.get("/safety/events", headers=ADMIN).json()
    assert events[0]["event_type"] == "OVERCROWDING"
    assert any("crowding" in item["message"].lower() for item in c.get("/notifications", headers=ADMIN).json())


def test_overcrowding_event_does_not_mark_room_fall_risk():
    reset()
    c = TestClient(app)
    created = c.post("/cv-events", headers=ADMIN, json={"room_id": "204", "event_type": "OVERCROWDING", "severity": "WARNING", "confidence": 0.8, "patient_state": "UNKNOWN", "previous_state": "UNKNOWN"})
    assert created.status_code == 201
    checks = c.get("/health/demo", headers=ADMIN).json()["checks"]
    assert checks["room_204_stable"] is True
    assert checks["no_active_cv_events"] is False
    notes = c.get("/notifications", headers=ADMIN).json()
    assert any(item["type"] == "WARNING" for item in notes)
    assert not any("fall risk" in item["message"].lower() and item["type"] == "CRITICAL" for item in notes)
