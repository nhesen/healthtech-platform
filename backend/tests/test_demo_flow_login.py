"""End-to-end walk through the eight README demo steps, entered through FIN login only."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import DB_PATH, ROOT, app


def reset():
    if DB_PATH.exists(): DB_PATH.unlink()
    from app.main import seed
    seed()


def sign_in(client: TestClient, fin: str, role: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"fin": fin, "role": role})
    assert response.status_code == 200, response.text
    return {"X-Demo-User": response.json()["email"]}


def test_eight_step_demo_flow_through_fin_login():
    reset(); c = TestClient(app)
    patient = sign_in(c, "1AZ0001", "PATIENT")
    doctor = sign_in(c, "2AZ0002", "DOCTOR")
    admin = sign_in(c, "3AZ0003", "HOSPITAL_ADMIN")

    # 1. Upload the synthetic lab report and confirm the extracted values.
    pdf = ROOT / "demo_documents" / "hasan_lab_report.pdf"
    assert pdf.exists(), "the bundled demo lab report is required for the demo flow"
    upload = c.post("/documents/upload", headers=patient, params={"patient_id": "patient_hasan"},
                    files={"file": ("hasan_lab_report.pdf", pdf.read_bytes(), "application/pdf")})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    extraction = upload.json()["extraction"]
    assert extraction["results"], "extraction must offer values for the patient to review"
    assert c.get(f"/documents/{document_id}", headers=patient).json()["processing_status"] != "CONFIRMED"
    body = {"results": extraction["results"], "report_date": extraction.get("report_date"), "source_name": extraction.get("source_name")}
    assert c.patch(f"/documents/{document_id}/review", headers=patient, json=body).status_code == 200
    confirmed = c.post(f"/documents/{document_id}/confirm", headers=patient, json=body)
    # results_created can be 0: the bundled report repeats seeded values, and identical
    # metric/value/date rows are deduplicated on purpose.
    assert confirmed.status_code == 200 and confirmed.json()["record_id"]
    assert c.get(f"/documents/{document_id}", headers=patient).json()["processing_status"] == "CONFIRMED"
    assert c.post(f"/documents/{document_id}/confirm", headers=patient, json=body).status_code == 409

    # 2. The HbA1c trend increases and endocrinology is suggested without a diagnosis.
    trends = c.get("/patients/patient_hasan/trends", headers=patient).json()
    hba1c = next(x for x in trends["trends"] if x["metric"] == "HbA1c")
    assert hba1c["trend"] == "increasing"
    assert "endocrin" in trends["care_navigation"]["suggested_specialty"].lower()

    # 3. Booking Dr. Leyla costs 60 AZN, of which insurance covers 48 AZN.
    estimate = c.get("/insurance/estimate", headers=patient, params={"patient_id": "patient_hasan", "doctor_id": "doctor_leyla"}).json()
    assert (estimate["service_price"], estimate["insurance_payment"], estimate["patient_payment"]) == (60.0, 48.0, 12.0)
    slot = next(x for x in c.get("/doctors/doctor_leyla/availability", headers=patient).json() if x["status"] == "AVAILABLE")["id"]
    appointment = c.post("/appointments", headers=patient, json={"doctor_id": "doctor_leyla", "slot_id": slot})
    assert appointment.status_code == 201
    appointment_id = appointment.json()["id"]

    # 4. The doctor brief stays closed until the patient grants matching consent.
    assert c.get("/doctors/patients/patient_hasan/brief", headers=doctor).status_code == 403
    assert c.post("/consents", headers=patient, json={"doctor_id": "doctor_leyla", "categories": ["LAB_RESULTS", "MEDICATIONS", "DOCTOR_NOTES"], "hours": 24}).status_code == 201
    brief = c.get("/doctors/patients/patient_hasan/brief", headers=doctor)
    assert brief.status_code == 200 and brief.json()["allowed_categories"]

    # 5. The clinician reviews and approves the consultation note.
    draft = c.post("/consultations", headers=doctor, json={"appointment_id": appointment_id, "doctor_notes": "Fatigue for two months. Metformin. Penicillin allergy.", "complete": False})
    assert draft.status_code == 201 and draft.json()["ai_draft"]
    for status in ["CHECKED_IN", "WAITING", "IN_PROGRESS"]:
        assert c.patch(f"/appointments/{appointment_id}/status", headers=doctor, json={"status": status}).status_code == 200
    approved = c.post("/consultations", headers=doctor, json={"appointment_id": appointment_id, "doctor_notes": "Reviewed.", "final_note": "Reviewed and approved by the clinician.", "complete": True})
    assert approved.status_code == 201
    assert any("approved" in (r.get("raw_text") or "").lower() or r["type"] == "CONSULTATION" for r in c.get("/patients/patient_hasan/timeline", headers=patient).json())

    # 6. The admin resolves patient #104's discharge blocker and releases the bed.
    available_before = c.get("/hospitals/hospital_caspian/capacity", headers=admin).json()["available"]
    assert c.patch("/tasks/task_104", headers=admin, json={"status": "IN_PROGRESS"}).status_code == 200
    assert c.post("/tasks/task_104/complete", headers=admin).status_code == 200
    assert c.post("/admissions/admission_104/discharge", headers=admin).status_code == 200
    assert c.post("/beds/bed_104/complete-cleaning", headers=admin).status_code == 200
    assert c.get("/hospitals/hospital_caspian/capacity", headers=admin).json()["available"] == available_before + 1

    # 7. A CV fall-risk event updates Room 204 for hospital operations.
    event = c.post("/cv-events", headers=admin, json={"hospital_id": "hospital_caspian", "room_id": "204", "event_type": "FALL_RISK", "severity": "HIGH", "confidence": 0.91, "patient_state": "STANDING", "previous_state": "SITTING"})
    assert event.status_code == 201
    assert any(x["status"] != "RESOLVED" for x in c.get("/safety/events", headers=admin).json())

    # 8. Demo reset restores the deterministic starting state.
    assert c.post("/demo/reset", headers=admin).status_code == 200
    assert c.get("/hospitals/hospital_caspian/capacity", headers=admin).json()["available"] == available_before
    assert all(x["status"] == "RESOLVED" for x in c.get("/safety/events", headers=admin).json() if x["room_id"] == "204") or not c.get("/safety/events", headers=admin).json()
    assert c.get("/auth/me", headers=admin).json()["role"] == "HOSPITAL_ADMIN"
