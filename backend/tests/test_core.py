import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app, DB_PATH


def reset():
    if DB_PATH.exists(): DB_PATH.unlink()
    from app.main import seed
    seed()


def test_trend_conflict_and_insurance():
    reset(); c=TestClient(app)
    patient={"X-Demo-User":"patient@demo.az"}; data=c.get("/patients/patient_hasan/trends",headers=patient).json()
    hba=next(x for x in data["trends"] if x["metric"]=="HbA1c")
    assert hba["change"]==0.5 and hba["trend"]=="increasing" and data["conflicts"]
    estimate=c.get("/insurance/estimate",headers=patient,params={"patient_id":"patient_hasan","doctor_id":"doctor_leyla"}).json()
    assert estimate["patient_payment"]==12.0


def test_booking_consent_and_doctor_brief():
    reset(); c=TestClient(app); slot=next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE")["id"]
    booked=c.post("/appointments",headers={"X-Demo-User":"patient@demo.az"},json={"doctor_id":"doctor_leyla","slot_id":slot}).json(); assert booked["status"]=="SCHEDULED"
    assert c.post("/appointments",headers={"X-Demo-User":"patient@demo.az"},json={"doctor_id":"doctor_leyla","slot_id":slot}).status_code==409
    c.post("/consents",headers={"X-Demo-User":"patient@demo.az"},json={"doctor_id":"doctor_leyla","categories":["LAB_RESULTS","MEDICATIONS","DOCTOR_NOTES"]})
    assert c.get("/doctors/patients/patient_hasan/brief",headers={"X-Demo-User":"doctor@demo.az"}).status_code==200


def test_discharge_and_cv_notification():
    reset(); c=TestClient(app); admin={"X-Demo-User":"admin@demo.az"}
    before=c.get("/hospitals/hospital_caspian/capacity",headers=admin).json()["available"]
    assert c.patch("/tasks/task_104",headers=admin,json={"status":"IN_PROGRESS"}).status_code==200
    assert c.post("/tasks/task_104/complete",headers=admin).status_code==200
    assert c.post("/admissions/admission_104/discharge",headers=admin).status_code==200
    cleaning=c.get("/hospitals/hospital_caspian/capacity",headers=admin).json()["cleaning"]
    assert cleaning==1
    assert c.post("/beds/bed_104/complete-cleaning",headers=admin).status_code==200
    assert c.get("/hospitals/hospital_caspian/capacity",headers=admin).json()["available"]==before+1
    assert c.post("/cv-events",headers=admin,json={"room_id":"204","event_type":"FALL_RISK","severity":"HIGH","confidence":.92}).status_code==201
    assert any(n["type"]=="CRITICAL" for n in c.get("/notifications",headers=admin).json())
