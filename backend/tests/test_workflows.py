import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "workflow_test.db")
from fastapi.testclient import TestClient
from app.main import DB_PATH, app, db, seed

PATIENT={"X-Demo-User":"patient@demo.az"}
DOCTOR={"X-Demo-User":"doctor@demo.az"}
ADMIN={"X-Demo-User":"admin@demo.az"}

def client():
    if DB_PATH.exists(): DB_PATH.unlink()
    seed()
    return TestClient(app)

def grant(c:TestClient):
    return c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":["LAB_RESULTS","MEDICATIONS","DOCTOR_NOTES"],"hours":24})

def test_rbac_and_consent_isolation():
    c=client()
    assert c.get("/patients/patient_hasan/lab-results",headers={"X-Demo-User":"patient104@demo.az"}).status_code==403
    assert c.get("/patients/patient_hasan/timeline",headers=ADMIN).status_code==403
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==403

def test_consent_category_filter_and_expiry():
    c=client(); slot=next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE")["id"]; c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot})
    consent=c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":["MEDICATIONS"],"hours":24}).json()
    assert c.get("/patients/patient_hasan/lab-results",headers=DOCTOR).status_code==403
    brief=c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).json()
    assert brief["relevant_metrics"]==[] and brief["allergies"]==[] and brief["medications"]
    with db() as conn: conn.execute("UPDATE consents SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",(consent["id"],))
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==403
    consent=grant(c).json()
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==200
    c.post(f"/consents/{consent['id']}/revoke",headers=PATIENT)
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==403

def test_booking_cancel_and_reschedule_release_slots():
    c=client(); slots=[x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE"]
    first,second=slots[0]["id"],slots[1]["id"]
    appointment=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":first}).json()
    assert c.patch(f"/appointments/{appointment['id']}/reschedule",headers=PATIENT,json={"slot_id":second}).status_code==200
    states={x["id"]:x["status"] for x in c.get("/doctors/doctor_leyla/availability").json()}
    assert states[first]=="AVAILABLE" and states[second]=="BOOKED"
    c.patch(f"/appointments/{appointment['id']}/cancel",headers=PATIENT)
    states={x["id"]:x["status"] for x in c.get("/doctors/doctor_leyla/availability").json()}
    assert states[second]=="AVAILABLE"
    replacement=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":second})
    assert replacement.status_code==201 and replacement.json()["id"]!=appointment["id"]

def test_document_upload_review_confirm_and_duplicate_protection():
    c=client(); content=(Path(__file__).parents[1]/"demo_documents"/"hasan_lab_report.pdf").read_bytes()
    files={"file":("hasan-labs.pdf",content,"application/pdf")}
    upload=c.post("/documents/upload?patient_id=patient_hasan",headers=PATIENT,files=files)
    assert upload.status_code==201
    payload=upload.json(); assert payload["status"]=="NEEDS_REVIEW" and len(payload["extraction"]["results"])==4
    assert c.post("/documents/upload?patient_id=patient_hasan",headers=PATIENT,files=files).status_code==409
    reviewed={"results":payload["extraction"]["results"],"report_date":"2026-08-19","source_name":"Synthetic demo lab"}
    assert c.patch(f"/documents/{payload['document_id']}/review",headers=PATIENT,json=reviewed).status_code==200
    confirmed=c.post(f"/documents/{payload['document_id']}/confirm",headers=PATIENT,json=reviewed)
    assert confirmed.status_code==200 and confirmed.json()["results_created"]==4
    assert c.post(f"/documents/{payload['document_id']}/confirm",headers=PATIENT,json=reviewed).status_code==409
    assert any(x["record_id"]==confirmed.json()["record_id"] for x in c.get("/patients/patient_hasan/lab-results",headers=PATIENT).json())
    with db() as conn:
        record=conn.execute("SELECT content_json FROM medical_records WHERE id=?",(confirmed.json()["record_id"],)).fetchone()
    assert payload["document_id"] in record["content_json"]

def test_consultation_requires_consent_and_doctor_approval():
    c=client(); slot=next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE")["id"]
    appointment=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot}).json()
    body={"appointment_id":appointment["id"],"doctor_notes":"Reviewed HbA1c trend.","final_note":"Patient was reviewed; follow-up discussed.","complete":True}
    assert c.post("/consultations",headers=DOCTOR,json=body).status_code==403
    grant(c)
    assert c.post("/consultations",headers=DOCTOR,json=body).status_code==409
    for state in ["CHECKED_IN","WAITING","IN_PROGRESS"]: c.patch(f"/appointments/{appointment['id']}/status",headers=DOCTOR,json={"status":state})
    result=c.post("/consultations",headers=DOCTOR,json=body)
    assert result.status_code==201 and result.json()["status"]=="COMPLETED"
    assert any(x["title"]=="Endocrinology consultation" for x in c.get("/patients/patient_hasan/timeline",headers=PATIENT).json())

def test_post_discharge_alert_notification_and_safety_deduplication():
    c=client(); slot=next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE")["id"]; c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot})
    low={"pain_score":2,"temperature":36.7,"medication_taken":True,"symptoms":"","notes":"ok"}; high={"pain_score":7,"temperature":38.2,"medication_taken":False,"symptoms":"fever","notes":"worse"}
    c.post("/post-discharge/patient_hasan",headers=PATIENT,json=low)
    assert c.post("/post-discharge/patient_hasan",headers=PATIENT,json=high).json()["requires_review"] is True
    assert any(n["type"]=="WARNING" for n in c.get("/notifications",headers=DOCTOR).json())
    event={"room_id":"204","event_type":"FALL_RISK","severity":"HIGH","confidence":.91,"patient_state":"STANDING","previous_state":"SITTING"}
    first=c.post("/cv-events",headers=ADMIN,json=event).json(); second=c.post("/cv-events",headers=ADMIN,json=event).json()
    assert second["status"]=="deduplicated"
    nurse=c.post(f"/cv-events/{first['id']}/send-nurse",headers=ADMIN).json(); again=c.post(f"/cv-events/{first['id']}/send-nurse",headers=ADMIN).json()
    assert nurse["id"]==again["id"] and again["deduplicated"] is True
    assert c.patch(f"/cv-events/{first['id']}/acknowledge",headers=ADMIN).json()["status"]=="ACKNOWLEDGED"
    assert c.patch(f"/cv-events/{first['id']}/resolve",headers=ADMIN).json()["status"]=="RESOLVED"

def test_notification_user_isolation_and_mark_all():
    c=client(); slot=next(x for x in c.get("/doctors/doctor_leyla/availability").json() if x["status"]=="AVAILABLE")["id"]
    c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot})
    assert c.get("/notifications/unread-count",headers=DOCTOR).json()["count"]>0
    assert c.patch("/notifications/read-all",headers=DOCTOR).json()["status"]=="ok"
    assert c.get("/notifications/unread-count",headers=DOCTOR).json()["count"]==0
    assert all(n.get("user_id")!="user_doctor" for n in c.get("/notifications",headers=PATIENT).json())
