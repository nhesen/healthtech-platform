"""Covers the endpoints wired into the UI while closing the README audit gaps."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import DB_PATH, app


def reset():
    if DB_PATH.exists(): DB_PATH.unlink()
    from app.main import seed
    seed()


PATIENT = {"X-Demo-User": "patient@demo.az"}
DOCTOR = {"X-Demo-User": "doctor@demo.az"}
ADMIN = {"X-Demo-User": "admin@demo.az"}


def test_insurance_plan_exposes_the_backend_coverage_matrix():
    reset(); c = TestClient(app)
    response = c.get("/insurance/plan", headers=PATIENT, params={"patient_id": "patient_hasan"})
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] and body["plan_name"]
    assert body["coverage"], "the plan must expose at least one coverage row"
    for row in body["coverage"]:
        assert row["service"] and 0 <= row["coverage_percent"] <= 100
    assert c.get("/insurance/plan", headers=ADMIN, params={"patient_id": "patient_hasan"}).status_code == 403


def test_lab_comparison_returns_a_change_per_metric():
    reset(); c = TestClient(app)
    history = c.get("/patients/patient_hasan/trends", headers=PATIENT).json()["trends"]
    hba1c = next(x for x in history if x["metric"] == "HbA1c")
    first, last = hba1c["history"][0]["result_date"], hba1c["history"][-1]["result_date"]
    body = c.get("/patients/patient_hasan/lab-comparison", headers=PATIENT, params={"from_date": first, "to_date": last}).json()
    entry = next(x for x in body["metrics"] if x["metric"] == "HbA1c")
    assert entry["direction"] == "up" and entry["change"] > 0
    assert body["explanation"]
    assert c.get("/patients/patient_hasan/lab-comparison", headers=PATIENT, params={"from_date": last, "to_date": first}).status_code == 422


def test_safety_events_expose_dispatched_nurse_tasks():
    reset(); c = TestClient(app)
    event = c.post("/cv-events", headers=ADMIN, json={"hospital_id": "hospital_caspian", "room_id": "204", "event_type": "FALL_RISK", "severity": "HIGH", "confidence": 0.91, "patient_state": "STANDING", "previous_state": "SITTING"}).json()
    events = c.get("/safety/events", headers=ADMIN).json()
    assert all("nurse_tasks" in x for x in events)
    assert next(x for x in events if x["id"] == event["id"])["nurse_tasks"] == []
    assert c.post(f"/cv-events/{event['id']}/send-nurse", headers=ADMIN).status_code == 200
    dispatched = next(x for x in c.get("/safety/events", headers=ADMIN).json() if x["id"] == event["id"])["nurse_tasks"]
    assert len(dispatched) == 1 and dispatched[0]["assigned_role"] == "NURSE" and dispatched[0]["status"] == "PENDING"


def test_admin_only_operational_views_are_reachable():
    reset(); c = TestClient(app)
    for path in ["/hospitals/hospital_caspian/departments", "/hospitals/hospital_caspian/recommendations", "/audit"]:
        assert c.get(path, headers=ADMIN).status_code == 200, path
        assert c.get(path, headers=DOCTOR).status_code == 403, path
    departments = c.get("/hospitals/hospital_caspian/departments", headers=ADMIN).json()
    assert departments and sum(x["total_beds"] for x in departments) == 200


def test_patient_can_revoke_a_granted_consent():
    reset(); c = TestClient(app)
    slot = next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"] == "AVAILABLE")["id"]
    c.post("/appointments", headers=PATIENT, json={"doctor_id": "doctor_leyla", "slot_id": slot})
    consent = c.post("/consents", headers=PATIENT, json={"doctor_id": "doctor_leyla", "categories": ["LAB_RESULTS"], "hours": 24}).json()
    assert c.get("/doctors/patients/patient_hasan/brief", headers=DOCTOR).status_code == 200
    assert c.post(f"/consents/{consent['id']}/revoke", headers=PATIENT).status_code == 200
    assert c.get("/doctors/patients/patient_hasan/brief", headers=DOCTOR).status_code == 403


def test_patient_can_reschedule_an_appointment_without_duplicating_it():
    reset(); c = TestClient(app)
    slots = [x["id"] for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"] == "AVAILABLE"]
    booked = c.post("/appointments", headers=PATIENT, json={"doctor_id": "doctor_leyla", "slot_id": slots[0]}).json()
    before = len(c.get("/appointments", headers=PATIENT).json())
    assert c.patch(f"/appointments/{booked['id']}/reschedule", headers=PATIENT, json={"slot_id": slots[1]}).status_code == 200
    after = c.get("/appointments", headers=PATIENT).json()
    assert len(after) == before
    assert next(x for x in after if x["id"] == booked["id"])["slot_id"] == slots[1]
