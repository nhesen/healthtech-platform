import os
from pathlib import Path

os.environ["DATABASE_URL"]=str(Path(__file__).parent/"security_test.db")
from fastapi.testclient import TestClient
from app.main import DB_PATH,app,db,seed

PATIENT={"X-Demo-User":"patient@demo.az"};OTHER_PATIENT={"X-Demo-User":"patient104@demo.az"}
DOCTOR={"X-Demo-User":"doctor@demo.az"};OTHER_DOCTOR={"X-Demo-User":"doctor_orxan@demo.az"};ADMIN={"X-Demo-User":"admin@demo.az"}

def fresh():
    if DB_PATH.exists():DB_PATH.unlink()
    seed();return TestClient(app)

def book_and_consent(c,categories=None):
    slot=c.get("/doctors/doctor_leyla/availability").json()[0]["id"]
    appointment=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot}).json()
    consent=c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":categories or ["LAB_RESULTS","MEDICATIONS","DIAGNOSES","DOCTOR_NOTES"],"hours":24}).json()
    return appointment,consent

def test_authentication_role_and_patient_isolation():
    c=fresh()
    for path in ["/auth/me","/patients/patient_hasan","/appointments","/notifications","/hospitals/hospital_caspian/capacity"]:
        assert c.get(path).status_code==401
    assert c.get("/patients/patient_hasan",headers=PATIENT).status_code==200
    assert c.get("/patients/patient_104",headers=PATIENT).status_code==403
    assert c.get("/hospitals/hospital_caspian/capacity",headers=PATIENT).status_code==403
    assert c.get("/hospitals/hospital_caspian/capacity",headers=DOCTOR).status_code==403
    assert c.get("/patients/patient_hasan/timeline",headers=ADMIN).status_code==403
    assert c.get("/auth/me",headers={"X-Demo-User":"unknown@demo.az"}).status_code==401
    response=c.get("/patients/patient_hasan",headers=PATIENT)
    assert response.headers["x-content-type-options"]=="nosniff" and response.headers["cache-control"]=="no-store"

def test_doctor_requires_matching_appointment_and_consent():
    c=fresh();assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==403
    appointment,consent=book_and_consent(c)
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==200
    assert c.get("/doctors/patients/patient_hasan/brief",headers=OTHER_DOCTOR).status_code==403
    assert c.get("/patients/patient_hasan/lab-results",headers=OTHER_DOCTOR).status_code==403
    c.post(f"/consents/{consent['id']}/revoke",headers=PATIENT)
    assert c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).status_code==403

def test_doctor_conflict_context_is_filtered_before_ai():
    c=fresh();book_and_consent(c,["LAB_RESULTS","DIAGNOSES"])
    brief=c.get("/doctors/patients/patient_hasan/brief",headers=DOCTOR).json()
    exposed=[record for warning in brief["warnings"] for record in warning["records"]]
    assert exposed and all(record["category"] in {"LAB_RESULTS","DIAGNOSES"} for record in exposed)
    assert all(record["title"]!="Annual check-up" for record in exposed)

def test_category_checks_require_every_category_and_old_consent_stays_revoked():
    c=fresh();_,first=book_and_consent(c,["LAB_RESULTS"])
    assert c.get("/patients/patient_hasan/trends",headers=DOCTOR).json()["conflicts"]==[]
    assert c.post("/ai/record-conflict-explanation",headers=DOCTOR,json={"patient_id":"patient_hasan"}).status_code==403
    second=c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":["DIAGNOSES"],"hours":24}).json()
    c.post(f"/consents/{second['id']}/revoke",headers=PATIENT)
    assert c.get("/patients/patient_hasan/lab-results",headers=DOCTOR).status_code==403

def test_hospital_admin_scope_is_enforced():
    c=fresh()
    with db() as conn:
        conn.execute("INSERT INTO hospitals VALUES(?,?,?,?,?)",("hospital_other","Other Demo Hospital","Ganja",0,0))
        conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",("user_admin_other","Other Admin","admin-other@demo.az","HOSPITAL_ADMIN",'{"hospital_id":"hospital_other"}',"2026-08-19T00:00:00+00:00"))
    other={"X-Demo-User":"admin-other@demo.az"}
    assert c.get("/hospitals/hospital_other/capacity",headers=ADMIN).status_code==403
    assert c.get("/hospitals/hospital_caspian/capacity",headers=other).status_code==403
    assert c.get("/hospitals/hospital_caspian/beds",headers=other).status_code==403
    assert c.get("/appointments",headers=other).json()==[]

def test_appointment_ownership_atomic_reschedule_and_transitions():
    c=fresh();slots=c.get("/doctors/doctor_leyla/availability").json();first,second=slots[0]["id"],slots[1]["id"]
    a=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":first}).json()
    c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":second})
    assert c.patch(f"/appointments/{a['id']}/cancel",headers=OTHER_PATIENT).status_code==403
    assert c.patch(f"/appointments/{a['id']}/cancel",headers=ADMIN).status_code==403
    assert c.patch(f"/appointments/{a['id']}/reschedule",headers=PATIENT,json={"slot_id":second}).status_code==409
    states={x["id"]:x["status"] for x in c.get("/doctors/doctor_leyla/availability").json()}
    assert states[first]=="BOOKED"
    assert c.patch(f"/appointments/{a['id']}/status",headers=DOCTOR,json={"status":"COMPLETED"}).status_code==409
    for state in ["CHECKED_IN","WAITING","IN_PROGRESS","COMPLETED"]:
        assert c.patch(f"/appointments/{a['id']}/status",headers=DOCTOR,json={"status":state}).status_code==200
    assert c.patch(f"/appointments/{a['id']}/status",headers=DOCTOR,json={"status":"WAITING"}).status_code==409

def test_queue_lab_comparison_and_consultation_draft_approval():
    c=fresh();slots=c.get("/doctors/doctor_leyla/availability").json()
    first=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slots[0]["id"]}).json()
    second=c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slots[1]["id"]}).json()
    queue=c.get(f"/appointments/{second['id']}/queue",headers=PATIENT).json();assert queue["queue_position"]==2 and queue["estimated_wait_minutes"]==15
    comparison=c.get("/patients/patient_hasan/lab-comparison?from_date=2024-12-31&to_date=2026-12-31",headers=PATIENT).json()
    hba=next(x for x in comparison["metrics"] if x["metric"]=="HbA1c");assert hba["change"]==0.9 and hba["direction"]=="up"
    consent=c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":["DOCTOR_NOTES"],"hours":24});assert consent.status_code==201
    before=len(c.get("/patients/patient_hasan/timeline",headers=PATIENT).json())
    draft=c.post("/consultations",headers=DOCTOR,json={"appointment_id":first["id"],"doctor_notes":"Draft review only","complete":False})
    assert draft.status_code==201 and draft.json()["status"]=="DRAFT" and len(c.get("/patients/patient_hasan/timeline",headers=PATIENT).json())==before
    for state in ["CHECKED_IN","WAITING","IN_PROGRESS"]: c.patch(f"/appointments/{first['id']}/status",headers=DOCTOR,json={"status":state})
    final=c.post("/consultations",headers=DOCTOR,json={"appointment_id":first["id"],"doctor_notes":"Reviewed","final_note":"Clinician approved note","complete":True})
    assert final.status_code==201 and final.json()["status"]=="COMPLETED" and len(c.get("/patients/patient_hasan/timeline",headers=PATIENT).json())==before+1

def test_document_content_validation_ownership_and_manual_image_fallback():
    c=fresh();bad={"file":("payload.pdf",b"MZ executable","application/pdf")}
    assert c.post("/documents/upload",headers=PATIENT,files=bad).status_code==422
    assert c.post("/documents/upload",headers=PATIENT,files={"file":("payload.exe",b"%PDF-1.4","application/pdf")}).status_code==415
    assert c.post("/documents/upload",headers=OTHER_PATIENT,files={"file":("mine.png",b"\x89PNG\r\n\x1a\nabc","image/png")}).status_code==403
    image={"file":("../../scan.png",b"\x89PNG\r\n\x1a\nsynthetic","image/png")}
    result=c.post("/documents/upload",headers=PATIENT,files=image)
    assert result.status_code==201 and result.json()["status"]=="UPLOADED" and result.json()["extraction"]["results"]==[]
    detail=c.get(f"/documents/{result.json()['document_id']}",headers=PATIENT).json()
    assert detail["filename"]=="scan.png" and ".." not in detail["filename"]
    huge=b"%PDF"+b"0"*(15*1024*1024)
    assert c.post("/documents/upload",headers=PATIENT,files={"file":("huge.pdf",huge,"application/pdf")}).status_code==413

def test_document_doctor_access_requires_relationship_and_category():
    c=fresh();pdf=(Path(__file__).parents[1]/"demo_documents"/"hasan_lab_report.pdf").read_bytes();files={"file":("lab.pdf",pdf,"application/pdf")}
    document=c.post("/documents/upload",headers=PATIENT,files=files).json()["document_id"]
    c.post("/consents",headers=PATIENT,json={"doctor_id":"doctor_leyla","categories":["LAB_RESULTS"],"hours":24})
    assert c.get(f"/documents/{document}",headers=DOCTOR).status_code==403
    slot=c.get("/doctors/doctor_leyla/availability").json()[0]["id"]
    c.post("/appointments",headers=PATIENT,json={"doctor_id":"doctor_leyla","slot_id":slot})
    detail=c.get(f"/documents/{document}",headers=DOCTOR)
    assert detail.status_code==200 and "storage_path" not in detail.json() and "file_hash" not in detail.json()

def test_task_discharge_bed_and_cv_state_transitions():
    c=fresh()
    assert c.post("/tasks/task_104/complete",headers=ADMIN).status_code==409
    assert c.post("/admissions/admission_104/discharge",headers=ADMIN).status_code==409
    assert c.patch("/tasks/task_104",headers=ADMIN,json={"status":"IN_PROGRESS"}).status_code==200
    assert c.patch("/tasks/task_104",headers=ADMIN,json={"status":"IN_PROGRESS"}).status_code==409
    assert c.post("/tasks/task_104/complete",headers=ADMIN).status_code==200
    discharged=c.post("/admissions/admission_104/discharge",headers=ADMIN).json()
    assert discharged["bed_status"]=="CLEANING"
    assert c.post("/beds/bed_104/complete-cleaning",headers=ADMIN).status_code==200
    assert c.post("/beds/bed_104/complete-cleaning",headers=ADMIN).status_code==409
    event=c.post("/cv-events",headers=ADMIN,json={"room_id":"204","confidence":.9}).json()
    assert c.patch(f"/cv-events/{event['id']}/resolve",headers=ADMIN).status_code==409
    assert c.patch(f"/cv-events/{event['id']}/acknowledge",headers=ADMIN).status_code==200
    assert c.patch(f"/cv-events/{event['id']}/acknowledge",headers=ADMIN).status_code==409
    assert c.patch(f"/cv-events/{event['id']}/resolve",headers=ADMIN).status_code==200

def test_cv_service_token_and_demo_protection(monkeypatch):
    c=fresh();monkeypatch.setenv("DEMO_MODE","false");monkeypatch.setenv("CV_SERVICE_TOKEN","test-service-token")
    payload={"hospital_id":"hospital_caspian","room_id":"204","confidence":.9}
    assert c.post("/cv-events",json=payload).status_code==401
    assert c.post("/cv-events",headers={"X-CV-Service-Key":"wrong"},json=payload).status_code==401
    service={"X-CV-Service-Key":"test-service-token"}
    assert c.post("/cv-events",headers=service,json={**payload,"confidence":1.1}).status_code==422
    assert c.post("/cv-events",headers=service,json={**payload,"hospital_id":"hospital_other"}).status_code==403
    assert c.post("/cv-events",headers=service,json=payload).status_code==201
    assert c.post("/demo/reset",headers=ADMIN).status_code in {401,404}
    assert c.get("/auth/demo-accounts").status_code==404

def test_notification_recipient_cannot_be_modified_by_another_user():
    c=fresh();book_and_consent(c);doctor_notes=c.get("/notifications",headers=DOCTOR).json();assert doctor_notes
    target=doctor_notes[0]["id"]
    assert c.patch(f"/notifications/{target}/read",headers=PATIENT).status_code==404
    assert all(x["id"]!=target for x in c.get("/notifications",headers=PATIENT).json())

def test_clean_seed_and_demo_reset_are_repeatable():
    c=fresh();c.post("/cv-events",headers=ADMIN,json={"room_id":"204","confidence":.9})
    assert c.post("/demo/reset",headers=ADMIN).status_code==200
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM beds").fetchone()[0]==200
        assert conn.execute("SELECT COUNT(*) FROM beds WHERE status='OCCUPIED'").fetchone()[0]==195
        assert conn.execute("SELECT COUNT(*) FROM cv_events").fetchone()[0]==0
        assert conn.execute("SELECT COUNT(*) FROM consents").fetchone()[0]==0
        assert conn.execute("SELECT COUNT(*) FROM availability WHERE status='AVAILABLE'").fetchone()[0]==4
