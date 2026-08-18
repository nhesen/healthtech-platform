import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "phase11_test.db")

from fastapi.testclient import TestClient

from app.main import DB_PATH, app, db, seed


PATIENT = {"X-Demo-User": "patient@demo.az"}
DOCTOR = {"X-Demo-User": "doctor@demo.az"}
ADMIN = {"X-Demo-User": "admin@demo.az"}
DEMO_NOTES = (
    "Chief complaint: Fatigue and concern about recent blood test results.\n"
    "Duration: 2 months.\nMedication: Metformin.\nAllergy: Penicillin."
)


def fresh() -> TestClient:
    if DB_PATH.exists():
        DB_PATH.unlink()
    seed()
    return TestClient(app)


def available_slot(client: TestClient) -> str:
    slots = client.get("/doctors/doctor_leyla/availability", headers=PATIENT).json()
    return next(slot["id"] for slot in slots if slot["status"] == "AVAILABLE")


def assert_initial_state(client: TestClient) -> None:
    readiness = client.get("/health/demo", headers=ADMIN)
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert all(readiness.json()["checks"].values())

    profile = client.get("/patients/patient_hasan", headers=PATIENT).json()
    assert profile["name"] == "Hasan M."
    assert profile["insurance_plan"] == "PLAN_PREMIUM"
    doctors = client.get("/doctors", headers=PATIENT).json()
    assert len(doctors) == 8
    leyla = next(doctor for doctor in doctors if doctor["id"] == "doctor_leyla")
    assert leyla["name"] == "Dr. Leyla Mammadova"
    assert leyla["specialty"] == "Endocrinology" and leyla["price"] == 60

    estimate = client.get(
        "/insurance/estimate",
        headers=PATIENT,
        params={"patient_id": "patient_hasan", "doctor_id": "doctor_leyla"},
    ).json()
    assert estimate["coverage_percent"] == 80
    assert estimate["insurance_payment"] == 48
    assert estimate["patient_payment"] == 12

    trends = client.get("/patients/patient_hasan/trends", headers=PATIENT).json()
    expected = {
        "HbA1c": [5.4, 5.8, 6.3],
        "Glucose": [89, 96, 108],
        "Vitamin D": [17, 21, 28],
        "Hemoglobin": [14.0, 14.1, 14.1],
    }
    for metric, values in expected.items():
        row = next(item for item in trends["trends"] if item["metric"] == metric)
        assert [point["value"] for point in row["history"]] == values
    assert trends["conflicts"]

    capacity = client.get("/hospitals/hospital_caspian/capacity", headers=ADMIN).json()
    assert capacity["total_beds"] == 200
    assert capacity["occupied"] == 195 and capacity["available"] == 5
    assert capacity["expected_discharges"] == 6 and capacity["delayed_discharges"] == 2
    forecast = client.get("/hospitals/hospital_caspian/forecast", headers=ADMIN).json()
    assert forecast["expected_usable_discharges"] == 4
    assert forecast["predicted_shortage"] == 3
    departments = client.get("/hospitals/hospital_caspian/departments", headers=ADMIN).json()
    department_counts = {row["name"]: row["total_beds"] for row in departments}
    assert {name: department_counts[name] for name in ("ICU", "Cardiology", "Surgery", "Neurology", "Internal Medicine")} == {
        "ICU": 20,
        "Cardiology": 40,
        "Surgery": 45,
        "Neurology": 35,
        "Internal Medicine": 60,
    }

    assert len([slot for slot in client.get("/doctors/doctor_leyla/availability", headers=PATIENT).json() if slot["status"] == "AVAILABLE"]) == 4
    assert client.get("/appointments", headers=PATIENT).json() == []
    assert client.get("/consents", headers=PATIENT).json() == []
    tasks = client.get("/tasks", headers=ADMIN).json()
    assert {task["id"]: task["status"] for task in tasks} == {"task_104": "PENDING", "task_207": "PENDING"}
    with db() as conn:
        assert conn.execute("SELECT safety_status FROM rooms WHERE id='room_204'").fetchone()[0] == "STABLE"
        assert conn.execute("SELECT COUNT(*) FROM cv_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM notifications WHERE id IN ('notification_patient_ready','notification_doctor_demo','notification_admin_capacity')").fetchone()[0] == 3


def run_complete_demo(client: TestClient) -> None:
    pdf = (Path(__file__).parents[1] / "demo_documents" / "hasan_lab_report.pdf").read_bytes()
    uploaded = client.post(
        "/documents/upload?patient_id=patient_hasan",
        headers=PATIENT,
        files={"file": ("hasan-demo-lab-report.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert [item["value"] for item in document["extraction"]["results"]] == [6.3, 108.0, 28.0, 14.1]
    review = {
        "results": document["extraction"]["results"],
        "report_date": document["extraction"]["report_date"],
        "source_name": "Synthetic demo lab",
    }
    confirmed = client.post(f"/documents/{document['document_id']}/confirm", headers=PATIENT, json=review)
    assert confirmed.status_code == 200
    assert confirmed.json()["results_created"] == 0  # the trusted seeded values are not duplicated

    appointment = client.post(
        "/appointments",
        headers=PATIENT,
        json={"doctor_id": "doctor_leyla", "slot_id": available_slot(client), "reason": "Review increasing lab trend"},
    )
    assert appointment.status_code == 201
    appointment_id = appointment.json()["id"]
    queue = client.get(f"/appointments/{appointment_id}/queue", headers=PATIENT).json()
    assert queue == {"queue_position": 4, "patients_before": 3, "estimated_wait_minutes": 45}
    advanced = client.post("/demo/queue/advance", headers=DOCTOR).json()
    assert advanced["queue_position"] == 3 and advanced["estimated_wait_minutes"] == 30
    advanced = client.post("/demo/queue/advance", headers=DOCTOR).json()
    assert advanced["queue_position"] == 2 and advanced["estimated_wait_minutes"] == 15

    consent = client.post(
        "/consents",
        headers=PATIENT,
        json={
            "doctor_id": "doctor_leyla",
            "categories": ["LAB_RESULTS", "MEDICATIONS", "DIAGNOSES", "DOCTOR_NOTES"],
            "hours": 24,
        },
    )
    assert consent.status_code == 201
    brief = client.get("/doctors/patients/patient_hasan/brief", headers=DOCTOR).json()
    assert brief["relevant_metrics"] and brief["medications"] and brief["warnings"]
    assert brief["allergies"][0]["name"] == "Penicillin"

    draft = client.post(
        "/consultations",
        headers=DOCTOR,
        json={"appointment_id": appointment_id, "doctor_notes": DEMO_NOTES, "complete": False},
    )
    assert draft.status_code == 201 and draft.json()["status"] == "DRAFT"
    messages = {item["message"] for item in draft.json()["missing_information"]}
    assert messages == {"Medication dosage not documented", "Allergy reaction not documented"}
    for state in ("CHECKED_IN", "WAITING", "IN_PROGRESS"):
        assert client.patch(f"/appointments/{appointment_id}/status", headers=DOCTOR, json={"status": state}).status_code == 200
    completed = client.post(
        "/consultations",
        headers=DOCTOR,
        json={"appointment_id": appointment_id, "doctor_notes": DEMO_NOTES, "final_note": "Clinician approved follow-up plan.", "complete": True},
    )
    assert completed.status_code == 201 and completed.json()["status"] == "COMPLETED"
    assert any(item["title"] == "Endocrinology consultation" for item in client.get("/patients/patient_hasan/timeline", headers=PATIENT).json())

    initial_forecast = client.get("/hospitals/hospital_caspian/forecast", headers=ADMIN).json()
    assert initial_forecast["predicted_shortage"] == 3
    assert client.patch("/tasks/task_104", headers=ADMIN, json={"status": "IN_PROGRESS"}).status_code == 200
    assert client.post("/tasks/task_104/complete", headers=ADMIN).status_code == 200
    improved_forecast = client.get("/hospitals/hospital_caspian/forecast", headers=ADMIN).json()
    assert improved_forecast["predicted_shortage"] < initial_forecast["predicted_shortage"]
    discharged = client.post("/admissions/admission_104/discharge", headers=ADMIN).json()
    assert discharged["bed_status"] == "CLEANING"
    assert client.post("/beds/bed_104/complete-cleaning", headers=ADMIN).status_code == 200
    final_capacity = client.get("/hospitals/hospital_caspian/capacity", headers=ADMIN).json()
    assert final_capacity["occupied"] == 194 and final_capacity["available"] == 6

    event = client.post(
        "/cv-events",
        headers=ADMIN,
        json={
            "hospital_id": "hospital_caspian",
            "room_id": "204",
            "event_type": "FALL_RISK",
            "severity": "HIGH",
            "confidence": 0.91,
            "patient_state": "STANDING",
            "previous_state": "SITTING",
            "metadata": {"source": "demo_control"},
        },
    ).json()
    with db() as conn:
        assert conn.execute("SELECT safety_status FROM rooms WHERE id='room_204'").fetchone()[0] == "HIGH_FALL_RISK"
    assert client.post(f"/cv-events/{event['id']}/send-nurse", headers=ADMIN).status_code == 200
    assert client.patch(f"/cv-events/{event['id']}/acknowledge", headers=ADMIN).status_code == 200
    assert client.patch(f"/cv-events/{event['id']}/resolve", headers=ADMIN).status_code == 200
    with db() as conn:
        assert conn.execute("SELECT safety_status FROM rooms WHERE id='room_204'").fetchone()[0] == "STABLE"


def test_phase11_seed_and_reset_are_idempotent_and_scoped() -> None:
    client = fresh()
    assert_initial_state(client)
    with db() as conn:
        conn.execute("INSERT INTO hospitals VALUES(?,?,?,?,?)", ("external_hospital", "External Hospital", "Ganja", 0, 0))
        conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", ("external_user", "External User", "external@example.com", "PATIENT", "{}", "2026-08-19T00:00:00+00:00"))
        conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", ("external_demo_domain", "External Demo Domain", "unrelated@demo.az", "PATIENT", "{}", "2026-08-19T00:00:00+00:00"))
        conn.execute("INSERT INTO departments VALUES(?,?,?)", ("external_department", "hospital_caspian", "Research"))
        conn.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?,?,?)", ("external_notification", None, "HOSPITAL_ADMIN", "hospital_caspian", "INFO", "Unrelated operational notice", None, None, None, "2026-08-19T00:00:00+00:00"))
    for _ in range(2):
        response = client.post("/demo/reset", headers=ADMIN)
        assert response.status_code == 200 and response.json()["ready"] is True
        assert_initial_state(client)
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM hospitals WHERE id='external_hospital'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM users WHERE id='external_user'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM users WHERE id='external_demo_domain'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM departments WHERE id='external_department'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM notifications WHERE id='external_notification'").fetchone()[0] == 1


def test_phase11_queue_post_discharge_and_complete_demo_twice() -> None:
    client = fresh()
    checkin = client.post(
        "/post-discharge/patient_followup",
        headers={"X-Demo-User": "followup@demo.az"},
        json={"pain_score": 7, "temperature": 38.2, "medication_taken": False, "symptoms": "fever", "notes": "Worse today"},
    )
    assert checkin.status_code == 201 and checkin.json() == {"trend": "worsening", "requires_review": True}
    assert any(item["type"] == "WARNING" for item in client.get("/notifications", headers=DOCTOR).json())

    for _ in range(2):
        reset = client.post("/demo/reset", headers=ADMIN)
        assert reset.status_code == 200 and reset.json()["ready"] is True
        run_complete_demo(client)


def test_phase11_demo_features_are_backend_disabled() -> None:
    client = fresh()
    previous = os.environ.get("DEMO_MODE")
    os.environ["DEMO_MODE"] = "false"
    try:
        assert client.post("/demo/reset", headers=ADMIN).status_code in {401, 404}
        assert client.get("/health/demo", headers=ADMIN).status_code in {401, 404}
        assert client.get("/demo/assets/lab-report", headers=PATIENT).status_code in {401, 404}
    finally:
        if previous is None:
            os.environ.pop("DEMO_MODE", None)
        else:
            os.environ["DEMO_MODE"] = previous
