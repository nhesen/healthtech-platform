from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .ai import ai_service
from .documents import ALLOWED, classify, extract_text, file_hash, parse_lab

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "uploads"; UPLOAD_DIR.mkdir(exist_ok=True)
db_url = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'healthtech.db'}")
DB_PATH = Path(db_url.replace("sqlite:///", ""))
AVERAGE_CONSULTATION_MINUTES = 15


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def rows(items: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(item) for item in items]


def one(conn: sqlite3.Connection, query: str, args: tuple = ()) -> dict[str, Any] | None:
    value = conn.execute(query, args).fetchone()
    return dict(value) if value else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, role TEXT NOT NULL, profile_json TEXT DEFAULT '{}', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hospitals (id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, emergency_waiting INTEGER DEFAULT 0, expected_incoming INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS departments (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, name TEXT NOT NULL, FOREIGN KEY(hospital_id) REFERENCES hospitals(id));
CREATE TABLE IF NOT EXISTS doctors (id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL, hospital_id TEXT NOT NULL, specialty TEXT NOT NULL, experience_years INTEGER NOT NULL, rating REAL NOT NULL, price REAL NOT NULL, accepted_plans TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS patients (id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL, dob TEXT, gender TEXT, phone TEXT, blood_type TEXT, emergency_contact TEXT, insurance_plan TEXT, allergies_json TEXT DEFAULT '[]', conditions_json TEXT DEFAULT '[]', medications_json TEXT DEFAULT '[]', FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS medical_records (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, record_date TEXT NOT NULL, hospital_id TEXT, doctor_id TEXT, category TEXT NOT NULL, content_json TEXT NOT NULL, raw_text TEXT, created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id));
CREATE TABLE IF NOT EXISTS lab_results (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, reference_range TEXT, result_date TEXT NOT NULL, record_id TEXT, FOREIGN KEY(patient_id) REFERENCES patients(id));
CREATE TABLE IF NOT EXISTS availability (id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY(doctor_id) REFERENCES doctors(id));
CREATE TABLE IF NOT EXISTS appointments (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, slot_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL, reason TEXT, cost_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(doctor_id) REFERENCES doctors(id), FOREIGN KEY(slot_id) REFERENCES availability(id));
CREATE TABLE IF NOT EXISTS consents (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, categories_json TEXT NOT NULL, starts_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS consultations (id TEXT PRIMARY KEY, appointment_id TEXT NOT NULL, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, transcript TEXT, doctor_notes TEXT, ai_draft TEXT, final_note TEXT, status TEXT NOT NULL, started_at TEXT, completed_at TEXT);
CREATE TABLE IF NOT EXISTS beds (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, department_id TEXT NOT NULL, room TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY(hospital_id) REFERENCES hospitals(id));
CREATE TABLE IF NOT EXISTS admissions (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, hospital_id TEXT NOT NULL, department_id TEXT NOT NULL, bed_id TEXT NOT NULL, admitted_at TEXT NOT NULL, expected_discharge_at TEXT, clinical_ready INTEGER DEFAULT 0, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discharge_blockers (id TEXT PRIMARY KEY, admission_id TEXT NOT NULL, blocker_type TEXT NOT NULL, responsible_role TEXT NOT NULL, status TEXT NOT NULL, estimated_minutes INTEGER NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, admission_id TEXT NOT NULL, blocker_id TEXT NOT NULL, assigned_role TEXT NOT NULL, priority TEXT NOT NULL, priority_score REAL NOT NULL, status TEXT NOT NULL, impact TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS notifications (id TEXT PRIMARY KEY, user_id TEXT, role TEXT, type TEXT NOT NULL, message TEXT NOT NULL, related_type TEXT, related_id TEXT, read_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkins (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, discharge_id TEXT, checkin_date TEXT NOT NULL, pain_score INTEGER NOT NULL, temperature REAL NOT NULL, medication_taken INTEGER NOT NULL, symptoms TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS cv_events (id TEXT PRIMARY KEY, room_id TEXT NOT NULL, event_type TEXT NOT NULL, severity TEXT NOT NULL, confidence REAL NOT NULL, occurred_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS safety_event_details (event_id TEXT PRIMARY KEY, patient_state TEXT, previous_state TEXT, status TEXT NOT NULL, acknowledged_at TEXT, acknowledged_by TEXT, resolved_at TEXT, metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS safety_tasks (id TEXT PRIMARY KEY, event_id TEXT NOT NULL, room_id TEXT NOT NULL, title TEXT NOT NULL, assigned_role TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, actor_id TEXT, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS medical_documents (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, uploaded_by TEXT NOT NULL, filename TEXT NOT NULL, mime_type TEXT NOT NULL, size INTEGER NOT NULL, storage_path TEXT NOT NULL, file_hash TEXT NOT NULL, document_type TEXT NOT NULL, processing_status TEXT NOT NULL, raw_text TEXT, extraction_json TEXT NOT NULL, confirmed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(patient_id,file_hash));
"""


def now() -> str: return datetime.now(timezone.utc).isoformat()
def uid(prefix: str) -> str: return f"{prefix}_{uuid4().hex[:12]}"
def audit(conn, actor, event, kind, entity, details=None):
    conn.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)", (uid("audit"), actor, event, kind, entity, json.dumps(details or {}), now()))
def notify(conn, *, user_id=None, role=None, kind="INFO", message: str, related_type=None, related_id=None):
    conn.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?,?)", (uid("note"), user_id, role, kind, message, related_type, related_id, None, now()))


def seed() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]: return
        created = now(); hospital = "hospital_caspian"
        users = [("user_patient", "Hasan Nurmammadov", "patient@demo.az", "PATIENT"), ("user_doctor", "Dr. Leyla Mammadova", "doctor@demo.az", "DOCTOR"), ("user_admin", "Aysel Karimova", "admin@demo.az", "HOSPITAL_ADMIN")]
        conn.executemany("INSERT INTO users VALUES(?,?,?,?,?,?)", [(a,b,c,d,"{}",created) for a,b,c,d in users])
        conn.execute("INSERT INTO hospitals VALUES(?,?,?,?,?)", (hospital,"Caspian Medical Center","Baku",12,12))
        departments = [("dept_endo",hospital,"Endocrinology"),("dept_cardio",hospital,"Cardiology"),("dept_internal",hospital,"Internal Medicine"),("dept_surgery",hospital,"Surgery"),("dept_icu",hospital,"ICU")]
        conn.executemany("INSERT INTO departments VALUES(?,?,?)", departments)
        conn.execute("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ("patient_hasan","user_patient","2004-04-12","Male","+994 50 555 01 01","A+","Nigar Nurmammadova, +994 50 555 01 02","PLAN_PREMIUM",json.dumps([{"name":"Penicillin","reaction":"rash","recorded":"2024"}]),json.dumps(["Family history of type 2 diabetes"]),json.dumps([{"name":"Metformin","dosage":"500 mg"}])))
        doctors = [("doctor_leyla","user_doctor",hospital,"Endocrinology",12,4.9,60.0,"PLAN_BASIC,PLAN_PLUS,PLAN_PREMIUM"),("doctor_orxan",None,hospital,"Cardiology",10,4.8,70.0,"PLAN_PLUS,PLAN_PREMIUM"),("doctor_nigar",None,hospital,"Dermatology",8,4.7,50.0,"PLAN_BASIC,PLAN_PREMIUM"),("doctor_elvin",None,hospital,"Neurology",14,4.9,75.0,"PLAN_PREMIUM"),("doctor_samira",None,hospital,"Internal Medicine",9,4.8,55.0,"PLAN_BASIC,PLAN_PLUS,PLAN_PREMIUM"),("doctor_ramil",None,hospital,"Surgery",15,4.8,85.0,"PLAN_PLUS,PLAN_PREMIUM"),("doctor_aysu",None,hospital,"Pediatrics",7,4.7,45.0,"PLAN_BASIC,PLAN_PLUS"),("doctor_tural",None,hospital,"Radiology",11,4.8,65.0,"PLAN_PREMIUM")]
        for d in doctors:
            if not d[1]:
                user_id=uid("user"); conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",(user_id,d[0].replace("doctor_","Dr. ").title(),d[0]+"@demo.az","DOCTOR","{}",created)); d=(d[0],user_id,*d[2:])
            conn.execute("INSERT INTO doctors VALUES(?,?,?,?,?,?,?,?)",d)
        metrics = {"HbA1c":[("2024-02-22",5.4),("2025-03-10",5.8),("2026-08-18",6.3)],"Glucose":[("2025-03-10",94),("2026-08-18",108)],"Vitamin D":[("2025-03-10",19),("2026-08-18",28)],"Cholesterol":[("2026-08-18",188)],"Hemoglobin":[("2026-08-18",14.2)]}
        for metric, values in metrics.items():
            for dt,value in values:
                record=uid("record"); conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(record,"patient_hasan","LAB_RESULT",f"{metric} result",dt,hospital,None,"LAB_RESULTS",json.dumps({"metric":metric,"value":value}),None,created)); conn.execute("INSERT INTO lab_results VALUES(?,?,?,?,?,?,?)",(uid("lab"),"patient_hasan",metric,value,"%" if metric=="HbA1c" else "mg/dL","4.0-5.6" if metric=="HbA1c" else "",dt,record))
        conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(uid("record"),"patient_hasan","DOCTOR_VISIT","Annual check-up","2025-03-10",hospital,"doctor_samira","DOCTOR_NOTES",json.dumps({"note":"Lifestyle review completed"}),"",created))
        # Explicit conflict for the demo.
        conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(uid("record"),"patient_hasan","CHECKUP","External check-up","2026-08-01",hospital,None,"LAB_RESULTS",json.dumps({"allergies":"NONE"}),"No known allergies",created))
        base=datetime.now(timezone.utc).replace(hour=11,minute=30,second=0,microsecond=0)+timedelta(days=1)
        for idx in range(4):
            start=base+timedelta(minutes=30*idx); conn.execute("INSERT INTO availability VALUES(?,?,?,?,?)",(f"slot_leyla_{idx}","doctor_leyla",start.isoformat(),(start+timedelta(minutes=30)).isoformat(),"AVAILABLE"))
        # 200 beds: 195 occupied, 5 available.
        for i in range(200):
            dept=departments[i%len(departments)][0]; conn.execute("INSERT INTO beds VALUES(?,?,?,?,?)",(f"bed_{i+1}",hospital,dept,f"{200+i//2}","OCCUPIED" if i<195 else "AVAILABLE"))
        for num, blocker, role, minutes, ready in [(104,"LAB_REVIEW_PENDING","DOCTOR",35,1),(207,"PHARMACY_PENDING","HOSPITAL_ADMIN",55,1)]:
            p=f"patient_{num}"; u=f"user_{num}"; conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",(u,f"Patient #{num}",f"patient{num}@demo.az","PATIENT","{}",created)); conn.execute("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(p,u,"1970-01-01","Other","","","","PLAN_BASIC","[]","[]","[]")); bed=f"bed_{num}"; adm=f"admission_{num}"; conn.execute("INSERT INTO admissions VALUES(?,?,?,?,?,?,?,?,?)",(adm,p,hospital,"dept_internal",bed,created,(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),ready,"ACTIVE")); bid=f"blocker_{num}"; conn.execute("INSERT INTO discharge_blockers VALUES(?,?,?,?,?,?,?,?)",(bid,adm,blocker,role,"OPEN",minutes,(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),None)); score=80 if num==104 else 60; conn.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)",(f"task_{num}","Review Lab Result" if num==104 else "Prepare Medication",adm,bid,role,"HIGH" if num==104 else "MEDIUM",score,"PENDING",f"Potentially frees 1 bed in ~{minutes} min",created,None))
        notify(conn,user_id="user_patient",kind="INFO",message="Your health timeline is ready.")


class DemoUser(BaseModel): id: str; name: str; email: str; role: str
def current_user(x_demo_user: str = Header("patient@demo.az")) -> DemoUser:
    with db() as conn:
        user=one(conn,"SELECT id,name,email,role FROM users WHERE email=?",(x_demo_user,))
    if not user: raise HTTPException(401,"Unknown demo user")
    return DemoUser(**user)
def require(*roles):
    def dep(user: DemoUser = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,"Insufficient role")
        return user
    return dep

def insurance(plan: str, specialty: str, price: float) -> dict:
    rates={"PLAN_BASIC":{"Endocrinology":.6,"Cardiology":.5},"PLAN_PLUS":{"Endocrinology":.7,"Cardiology":.7},"PLAN_PREMIUM":{"Endocrinology":.8,"Cardiology":.8,"Internal Medicine":.8}}
    coverage=rates.get(plan,{}).get(specialty,.4); paid=round(price*coverage,2)
    return {"plan":plan,"service":specialty,"service_price":price,"coverage_percent":int(coverage*100),"insurance_payment":paid,"patient_payment":round(price-paid,2)}
def active_consent(conn, patient_id: str, doctor_id: str) -> list[str]:
    c=one(conn,"SELECT categories_json FROM consents WHERE patient_id=? AND doctor_id=? AND status='ACTIVE' AND revoked_at IS NULL AND expires_at>? ORDER BY created_at DESC",(patient_id,doctor_id,now()))
    return json.loads(c["categories_json"]) if c else []
def trends(conn, patient_id: str) -> list[dict]:
    result=[]
    for metric in rows(conn.execute("SELECT DISTINCT metric FROM lab_results WHERE patient_id=?",(patient_id,)).fetchall()):
        values=rows(conn.execute("SELECT value,result_date,unit FROM lab_results WHERE patient_id=? AND metric=? ORDER BY result_date",(patient_id,metric["metric"])).fetchall())
        if not values: continue
        current=values[-1]; previous=values[-2] if len(values)>1 else None; change=round(current["value"]-previous["value"],2) if previous else 0
        result.append({"metric":metric["metric"],"current":current["value"],"previous":previous["value"] if previous else None,"change":change,"percent_change":round(change/previous["value"]*100,1) if previous and previous["value"] else None,"trend":"increasing" if change>0 else "decreasing" if change<0 else "stable","history":values})
    return result
def conflicts(conn, patient_id: str) -> list[dict]:
    allergy=one(conn,"SELECT allergies_json FROM patients WHERE id=?",(patient_id,)); records=rows(conn.execute("SELECT id,title,record_date,raw_text,content_json FROM medical_records WHERE patient_id=?",(patient_id,)).fetchall())
    if allergy and json.loads(allergy["allergies_json"]) and any("No known allergies" in (r["raw_text"] or "") for r in records):
        return [{"type":"record_conflict","field":"allergies","severity":"requires_review","message":"Penicillin allergy conflicts with a later 'No known allergies' record.","records":records}]
    return []
def specialty_for(trend_data: list[dict]) -> dict:
    abnormal=[t for t in trend_data if t["metric"] in {"HbA1c","Glucose"} and t["trend"]=="increasing"]
    return {"suggested_specialty":"Endocrinology","reason":"Recent HbA1c or glucose measurements are increasing. This is a navigation suggestion, not a diagnosis."} if abnormal else {"suggested_specialty":"Internal Medicine","reason":"A general clinical review may be useful."}
def capacity(conn,hospital_id: str) -> dict:
    states=rows(conn.execute("SELECT status,COUNT(*) count FROM beds WHERE hospital_id=? GROUP BY status",(hospital_id,)).fetchall()); counts={r["status"]:r["count"] for r in states}; expected=conn.execute("SELECT COUNT(*) FROM admissions WHERE hospital_id=? AND status IN ('ACTIVE','READY_FOR_DISCHARGE') AND clinical_ready=1",(hospital_id,)).fetchone()[0]; blocked=conn.execute("SELECT COUNT(*) FROM discharge_blockers b JOIN admissions a ON a.id=b.admission_id WHERE a.hospital_id=? AND b.status='OPEN'",(hospital_id,)).fetchone()[0]; h=one(conn,"SELECT emergency_waiting,expected_incoming FROM hospitals WHERE id=?",(hospital_id,))
    return {"total_beds":sum(counts.values()),"occupied":counts.get("OCCUPIED",0),"available":counts.get("AVAILABLE",0),"cleaning":counts.get("CLEANING",0),"expected_discharges":expected,"delayed_discharges":blocked,"emergency_waiting":h["emergency_waiting"],"expected_incoming":h["expected_incoming"]}
def priority_score(blocker: dict, cap: dict) -> float:
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(blocker["created_at"])).total_seconds()/60
    return round(min(100,35 + min(age,180)/6 + (20 if cap["available"]<10 else 0) + (15 if blocker["estimated_minutes"]<=40 else 5)),1)


app=FastAPI(title="HealthTech Backbone",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000"],allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def boot(): seed()

class AppointmentIn(BaseModel): doctor_id:str; slot_id:str; reason:str="Endocrinology consultation"
class RescheduleIn(BaseModel): slot_id:str
class AppointmentStatusIn(BaseModel): status:Literal["SCHEDULED","CHECKED_IN","WAITING","IN_PROGRESS","COMPLETED","CANCELLED"]
class ConsentIn(BaseModel): doctor_id:str; categories:list[str]; hours:int=Field(24,ge=1,le=168)
class ConsultationIn(BaseModel): appointment_id:str; transcript:str=""; doctor_notes:str=""; final_note:str|None=None; complete:bool=False
class CheckinIn(BaseModel): pain_score:int=Field(ge=1,le=10); temperature:float; medication_taken:bool; symptoms:str=""; notes:str=""
class CVEventIn(BaseModel): room_id:str; event_type:Literal["FALL_RISK","PATIENT_STANDING","OUT_OF_BED"]="FALL_RISK"; severity:Literal["HIGH","CRITICAL","WARNING","MEDIUM"]="HIGH"; confidence:float=Field(ge=0,le=1); patient_state:str="STANDING"; previous_state:str="SITTING"; timestamp:datetime|None=None; metadata:dict[str,Any]=Field(default_factory=dict)
class ReadIn(BaseModel): ids:list[str]=[]
class AITextIn(BaseModel): patient_id:str|None=None; notes:str=""; missing:list[str]=[]; task_id:str|None=None
class DocumentConfirmIn(BaseModel): results:list[dict[str,Any]]=[]; report_date:str|None=None; source_name:str|None=None

@app.get("/health")
def health(): return {"status":"ok","demo_mode":True}
@app.get("/auth/me")
def me(user:DemoUser=Depends(current_user)): return user
@app.get("/auth/demo-accounts")
def accounts():
    with db() as conn: return rows(conn.execute("SELECT name,email,role FROM users WHERE email IN ('patient@demo.az','doctor@demo.az','admin@demo.az')").fetchall())
@app.get("/patients/{patient_id}")
def patient(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        p=one(conn,"SELECT p.*,u.name,u.email FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,))
    if not p: raise HTTPException(404,"Patient not found")
    if user.role=="PATIENT" and p["user_id"]!=user.id: raise HTTPException(403,"Only your profile is available")
    return p
@app.get("/patients/{patient_id}/timeline")
def timeline(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn: return rows(conn.execute("SELECT * FROM medical_records WHERE patient_id=? ORDER BY record_date DESC",(patient_id,)).fetchall())
@app.get("/patients/{patient_id}/lab-results")
def labs(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn: return rows(conn.execute("SELECT * FROM lab_results WHERE patient_id=? ORDER BY result_date DESC",(patient_id,)).fetchall())
def document_access(conn, document:dict, user:DemoUser):
    if user.role=="PATIENT":
        if one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(document["patient_id"],user.id)):return
    if user.role=="DOCTOR":
        doctor=one(conn,"SELECT id FROM doctors WHERE user_id=?",(user.id,))
        if doctor and "LAB_RESULTS" in active_consent(conn,document["patient_id"],doctor["id"]):return
    raise HTTPException(403,"Document access is not authorized")
@app.post("/documents/upload",status_code=201)
async def upload_document(file:UploadFile=File(...),patient_id:str="patient_hasan",user:DemoUser=Depends(current_user)):
    if file.content_type not in ALLOWED: raise HTTPException(415,"Please upload a PDF, PNG, or JPG file.")
    data=await file.read()
    if len(data)>15*1024*1024: raise HTTPException(413,"Maximum file size is 15 MB.")
    with db() as conn:
        if user.role=="PATIENT":
            if not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(patient_id,user.id)):raise HTTPException(403,"Patient mismatch")
        elif user.role=="DOCTOR":
            doctor=one(conn,"SELECT id FROM doctors WHERE user_id=?",(user.id,))
            if not doctor or "LAB_RESULTS" not in active_consent(conn,patient_id,doctor["id"]):raise HTTPException(403,"Valid lab-result consent is required")
        else: raise HTTPException(403,"Only patient or authorized doctor can upload")
        digest=file_hash(data); existing=one(conn,"SELECT id FROM medical_documents WHERE patient_id=? AND file_hash=?",(patient_id,digest))
        if existing: raise HTTPException(409,"This document appears to have already been uploaded.")
        did=uid("doc"); safe_name=re.sub(r"[^A-Za-z0-9._-]","_",file.filename or "document"); target=UPLOAD_DIR/f"{did}_{safe_name}"; target.write_bytes(data); text=extract_text(data,file.content_type or ""); dtype,confidence=classify(text); parsed=parse_lab(text) if dtype=="LAB_REPORT" else {"results":[]}; parsed.update({"document_type":dtype,"confidence":confidence}); state="NEEDS_REVIEW" if parsed["results"] else "UPLOADED"; conn.execute("INSERT INTO medical_documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(did,patient_id,user.id,safe_name,file.content_type,len(data),str(target),digest,dtype,state,text,json.dumps(parsed),None,now(),now())); notify(conn,user_id=user.id,kind="INFO",message="Document processed. Review extracted information before confirming.",related_type="document",related_id=did); audit(conn,user.id,"DOCUMENT_UPLOADED","document",did,{"type":dtype}); return {"document_id":did,"status":state,"extraction":parsed}
@app.get("/documents")
def documents(patient_id:str="patient_hasan",user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role=="PATIENT" and not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(patient_id,user.id)):raise HTTPException(403,"Patient mismatch")
        return rows(conn.execute("SELECT id,filename,document_type,processing_status,created_at,confirmed_at FROM medical_documents WHERE patient_id=? ORDER BY created_at DESC",(patient_id,)).fetchall())
@app.get("/documents/{document_id}")
def document_detail(document_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        doc=one(conn,"SELECT * FROM medical_documents WHERE id=?",(document_id,));
        if not doc:raise HTTPException(404,"Document not found")
        document_access(conn,doc,user); return doc
@app.post("/documents/{document_id}/confirm")
def confirm_document(document_id:str,payload:DocumentConfirmIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        doc=one(conn,"SELECT * FROM medical_documents WHERE id=?",(document_id,));
        if not doc:raise HTTPException(404,"Document not found")
        document_access(conn,doc,user); extracted=json.loads(doc["extraction_json"]); results=payload.results or extracted.get("results",[]); report_date=payload.report_date or date.today().isoformat(); source=payload.source_name or "Uploaded document"; record=uid("record"); conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(record,doc["patient_id"],"LAB_RESULT",doc["filename"],report_date,None,None,"LAB_RESULTS",json.dumps({"source_document_id":document_id,"results":results}),doc["raw_text"],now()))
        for item in results:
            if not item.get("test_name") or item.get("value") is None:continue
            conn.execute("INSERT INTO lab_results VALUES(?,?,?,?,?,?,?)",(uid("lab"),doc["patient_id"],item["test_name"],float(item["value"]),item.get("unit","") or "",item.get("reference_text","") or "",report_date,record))
        conn.execute("UPDATE medical_documents SET processing_status='CONFIRMED',confirmed_at=?,updated_at=? WHERE id=?",(now(),now(),document_id)); notify(conn,user_id=user.id,kind="SUCCESS",message="Lab results added to your health timeline.",related_type="document",related_id=document_id); audit(conn,user.id,"DOCUMENT_CONFIRMED","document",document_id,{"result_count":len(results),"source":source}); return {"status":"CONFIRMED","record_id":record,"results_created":len(results)}
@app.get("/patients/{patient_id}/trends")
def lab_trends(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn: return {"trends":trends(conn,patient_id),"conflicts":conflicts(conn,patient_id),"care_navigation":specialty_for(trends(conn,patient_id))}
@app.get("/patients/{patient_id}/overview")
def patient_overview(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        p=one(conn,"SELECT p.*,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,))
        if not p or (user.role=="PATIENT" and p["user_id"]!=user.id): raise HTTPException(403,"Profile unavailable")
        upcoming=one(conn,"SELECT a.*,u.name doctor_name,d.specialty,h.name hospital_name,s.starts_at FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id JOIN availability s ON s.id=a.slot_id WHERE a.patient_id=? AND a.status NOT IN ('CANCELLED','COMPLETED') ORDER BY s.starts_at LIMIT 1",(patient_id,))
        records=rows(conn.execute("SELECT type,title,record_date,category FROM medical_records WHERE patient_id=? ORDER BY record_date DESC LIMIT 4",(patient_id,)).fetchall())
        return {"patient":{"id":patient_id,"name":p["name"],"insurance_plan":p["insurance_plan"],"allergies":json.loads(p["allergies_json"]),"conditions":json.loads(p["conditions_json"]),"medications":json.loads(p["medications_json"])},"upcoming_appointment":upcoming,"recent_activity":records,"insight_count":len(conflicts(conn,patient_id))+sum(1 for x in trends(conn,patient_id) if x["trend"]=="increasing")}
@app.get("/patients/{patient_id}/lab-comparison")
def lab_comparison(patient_id:str,from_date:str,to_date:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        all_labs=rows(conn.execute("SELECT metric,value,unit,result_date,reference_range FROM lab_results WHERE patient_id=? ORDER BY result_date",(patient_id,)).fetchall()); result=[]
        for metric in sorted({x["metric"] for x in all_labs}):
            series=[x for x in all_labs if x["metric"]==metric]; old=max((x for x in series if x["result_date"]<=from_date),key=lambda x:x["result_date"],default=None); new=max((x for x in series if x["result_date"]<=to_date),key=lambda x:x["result_date"],default=None)
            if old and new: result.append({"metric":metric,"from":old,"to":new,"change":round(new["value"]-old["value"],2),"direction":"up" if new["value"]>old["value"] else "down" if new["value"]<old["value"] else "same"})
        changed=[x["metric"] for x in result if x["change"]]
        return {"from_date":from_date,"to_date":to_date,"metrics":result,"explanation":f"{len(changed)} metrics changed between these tests. This comparison does not provide a diagnosis."}
@app.get("/doctors")
def doctor_directory(specialty:str|None=None,q:str|None=None,hospital_id:str|None=None,max_price:float|None=None):
    with db() as conn:
        sql="SELECT d.*,u.name,h.name hospital_name FROM doctors d JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id"; args=()
        clauses=[]
        if specialty: clauses.append("d.specialty=?"); args+=(specialty,)
        if q: clauses.append("(u.name LIKE ? OR d.specialty LIKE ? OR h.name LIKE ?)"); args+=(f"%{q}%",f"%{q}%",f"%{q}%")
        if hospital_id: clauses.append("d.hospital_id=?"); args+=(hospital_id,)
        if max_price: clauses.append("d.price<=?"); args+=(max_price,)
        if clauses: sql+=" WHERE "+" AND ".join(clauses)
        return rows(conn.execute(sql,args).fetchall())
@app.get("/doctors/{doctor_id}/availability")
def doctor_slots(doctor_id:str):
    with db() as conn: return rows(conn.execute("SELECT * FROM availability WHERE doctor_id=? ORDER BY starts_at",(doctor_id,)).fetchall())
@app.get("/insurance/estimate")
def insurance_estimate(patient_id:str,doctor_id:str):
    with db() as conn:
        p=one(conn,"SELECT insurance_plan FROM patients WHERE id=?",(patient_id,)); d=one(conn,"SELECT specialty,price FROM doctors WHERE id=?",(doctor_id,))
        if not p or not d: raise HTTPException(404,"Patient or doctor not found")
        return insurance(p["insurance_plan"],d["specialty"],d["price"])
@app.post("/appointments",status_code=201)
def book(payload:AppointmentIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        p=one(conn,"SELECT id,insurance_plan FROM patients WHERE user_id=?",(user.id,)); slot=one(conn,"SELECT * FROM availability WHERE id=? AND doctor_id=?",(payload.slot_id,payload.doctor_id)); d=one(conn,"SELECT specialty,price FROM doctors WHERE id=?",(payload.doctor_id,))
        if not slot or slot["status"]!="AVAILABLE": raise HTTPException(409,"Slot is no longer available")
        cost=insurance(p["insurance_plan"],d["specialty"],d["price"]); aid=uid("appt"); conn.execute("INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?)",(aid,p["id"],payload.doctor_id,payload.slot_id,"SCHEDULED",payload.reason,json.dumps(cost),now())); conn.execute("UPDATE availability SET status='BOOKED' WHERE id=?",(payload.slot_id,)); notify(conn,user_id=user.id,kind="SUCCESS",message="Appointment confirmed.",related_type="appointment",related_id=aid); doctor_user=one(conn,"SELECT user_id FROM doctors WHERE id=?",(payload.doctor_id,)); notify(conn,user_id=doctor_user["user_id"],kind="TASK",message="New appointment scheduled.",related_type="appointment",related_id=aid); audit(conn,user.id,"APPOINTMENT_BOOKED","appointment",aid,cost)
        return {"id":aid,"status":"SCHEDULED","cost":cost,"consent_suggested":True}
@app.get("/appointments")
def list_appointments(user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role=="PATIENT": q="SELECT a.*,u.name doctor_name,s.starts_at FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=(SELECT user_id FROM doctors WHERE id=a.doctor_id) JOIN availability s ON s.id=a.slot_id WHERE p.user_id=?"; data=rows(conn.execute(q,(user.id,)).fetchall())
        elif user.role=="DOCTOR": data=rows(conn.execute("SELECT a.*,u.name patient_name,s.starts_at FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=p.user_id JOIN availability s ON s.id=a.slot_id WHERE d.user_id=?",(user.id,)).fetchall())
        else: data=rows(conn.execute("SELECT * FROM appointments").fetchall())
        return data
@app.patch("/appointments/{appointment_id}/cancel")
def cancel(appointment_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,));
        if not a: raise HTTPException(404,"Appointment not found")
        conn.execute("UPDATE appointments SET status='CANCELLED' WHERE id=?",(appointment_id,)); conn.execute("UPDATE availability SET status='AVAILABLE' WHERE id=?",(a["slot_id"],)); audit(conn,user.id,"APPOINTMENT_CANCELLED","appointment",appointment_id); return {"status":"CANCELLED"}
@app.patch("/appointments/{appointment_id}/status")
def appointment_status(appointment_id:str,payload:AppointmentStatusIn,user:DemoUser=Depends(require("DOCTOR","HOSPITAL_ADMIN"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,));
        if not a: raise HTTPException(404,"Appointment not found")
        conn.execute("UPDATE appointments SET status=? WHERE id=?",(payload.status,appointment_id)); patient_user=one(conn,"SELECT user_id FROM patients WHERE id=?",(a["patient_id"],));
        if payload.status in ("CHECKED_IN","WAITING","COMPLETED"): notify(conn,user_id=patient_user["user_id"],kind="INFO",message=f"Appointment status updated: {payload.status.replace('_',' ').title()}.",related_type="appointment",related_id=appointment_id)
        audit(conn,user.id,"APPOINTMENT_STATUS_UPDATED","appointment",appointment_id,{"status":payload.status}); return {"id":appointment_id,"status":payload.status}
@app.patch("/appointments/{appointment_id}/reschedule")
def reschedule(appointment_id:str,payload:RescheduleIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,)); slot=one(conn,"SELECT * FROM availability WHERE id=?",(payload.slot_id,))
        if not a or not slot or slot["doctor_id"]!=a["doctor_id"]: raise HTTPException(404,"Appointment or slot not found")
        if slot["status"]!="AVAILABLE": raise HTTPException(409,"Slot is no longer available")
        conn.execute("UPDATE availability SET status='AVAILABLE' WHERE id=?",(a["slot_id"],)); conn.execute("UPDATE availability SET status='BOOKED' WHERE id=?",(payload.slot_id,)); conn.execute("UPDATE appointments SET slot_id=? WHERE id=?",(payload.slot_id,appointment_id)); notify(conn,user_id=user.id,kind="INFO",message="Appointment rescheduled.",related_type="appointment",related_id=appointment_id); audit(conn,user.id,"APPOINTMENT_RESCHEDULED","appointment",appointment_id); return {"status":"SCHEDULED","slot_id":payload.slot_id}
@app.get("/appointments/{appointment_id}/queue")
def queue(appointment_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        a=one(conn,"SELECT a.*,s.starts_at FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.id=?",(appointment_id,));
        before=conn.execute("SELECT COUNT(*) FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.doctor_id=? AND date(s.starts_at)=date(?) AND s.starts_at<? AND a.status NOT IN ('CANCELLED')",(a["doctor_id"],a["starts_at"],a["starts_at"])).fetchone()[0]
        return {"queue_position":before+1,"patients_before":before,"estimated_wait_minutes":before*AVERAGE_CONSULTATION_MINUTES}
@app.post("/consents",status_code=201)
def grant_consent(payload:ConsentIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        p=one(conn,"SELECT id FROM patients WHERE user_id=?",(user.id,)); cid=uid("consent"); start=datetime.now(timezone.utc); expires=start+timedelta(hours=payload.hours); conn.execute("INSERT INTO consents VALUES(?,?,?,?,?,?,?,?,?)",(cid,p["id"],payload.doctor_id,json.dumps(payload.categories),start.isoformat(),expires.isoformat(),None,"ACTIVE",now())); audit(conn,user.id,"CONSENT_GRANTED","consent",cid,{"categories":payload.categories}); return {"id":cid,"expires_at":expires.isoformat(),"status":"ACTIVE"}
@app.get("/consents")
def list_consents(user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:return rows(conn.execute("SELECT c.*,u.name doctor_name,d.specialty,h.name hospital_name FROM consents c JOIN doctors d ON d.id=c.doctor_id JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id JOIN patients p ON p.id=c.patient_id WHERE p.user_id=? ORDER BY c.created_at DESC",(user.id,)).fetchall())
@app.post("/consents/{consent_id}/revoke")
def revoke_consent(consent_id:str,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        c=one(conn,"SELECT c.* FROM consents c JOIN patients p ON p.id=c.patient_id WHERE c.id=? AND p.user_id=?",(consent_id,user.id))
        if not c: raise HTTPException(404,"Consent not found")
        conn.execute("UPDATE consents SET status='REVOKED',revoked_at=? WHERE id=?",(now(),consent_id)); audit(conn,user.id,"CONSENT_REVOKED","consent",consent_id); return {"status":"REVOKED"}
@app.get("/doctors/patients/{patient_id}/brief")
def doctor_brief(patient_id:str,user:DemoUser=Depends(require("DOCTOR"))):
    with db() as conn:
        d=one(conn,"SELECT * FROM doctors WHERE user_id=?",(user.id,)); allowed=active_consent(conn,patient_id,d["id"])
        if not allowed: raise HTTPException(403,"No active patient consent")
        p=one(conn,"SELECT p.*,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,)); data=trends(conn,patient_id); relevant=[x for x in data if x["metric"] in ("HbA1c","Glucose")] if d["specialty"]=="Endocrinology" else data; records=rows(conn.execute("SELECT * FROM medical_records WHERE patient_id=? AND category IN (%s) ORDER BY record_date DESC" % ",".join("?"*len(allowed)),(patient_id,*allowed)).fetchall()); audit(conn,user.id,"DOCTOR_VIEWED_RECORD","patient",patient_id,{"categories":allowed})
        context={"relevant_metrics":relevant,"medications":json.loads(p["medications_json"]) if "MEDICATIONS" in allowed else [],"allergies":json.loads(p["allergies_json"])}; ai=ai_service.generate("patient_brief",context)
        return {"patient":{"id":patient_id,"name":p["name"],"dob":p["dob"]},"reason_for_visit":"Endocrinology consultation","allowed_categories":allowed,"important_history":[r["title"] for r in records],"warnings":conflicts(conn,patient_id),**ai.content,"ai":ai.model_dump()}
@app.post("/consultations",status_code=201)
def consultation(payload:ConsultationIn,user:DemoUser=Depends(require("DOCTOR"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(payload.appointment_id,)); d=one(conn,"SELECT id FROM doctors WHERE user_id=?",(user.id,));
        if not a or a["doctor_id"]!=d["id"]: raise HTTPException(403,"Appointment unavailable")
        missing=[]; text=(payload.transcript+" "+payload.doctor_notes).lower()
        if "medication" in text and not any(x in text for x in ["mg","ml","dose","dosage"]): missing.append("Medication dosage missing")
        if "allergy" in text and not any(x in text for x in ["rash","reaction","anaphyl"]): missing.append("Allergy reaction not documented")
        if "symptom" in text and not any(x in text for x in ["day","week","month","duration"]): missing.append("Symptom duration not documented")
        cid=uid("consult"); state="COMPLETED" if payload.complete and payload.final_note else "DRAFT"; conn.execute("INSERT INTO consultations VALUES(?,?,?,?,?,?,?,?,?,?,?)",(cid,a["id"],a["patient_id"],d["id"],payload.transcript,payload.doctor_notes,"Structured draft: "+payload.doctor_notes,payload.final_note,state,now(),now() if state=="COMPLETED" else None))
        if state=="COMPLETED": conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(uid("record"),a["patient_id"],"DOCTOR_VISIT","Endocrinology consultation",date.today().isoformat(),None,d["id"],"DOCTOR_NOTES",json.dumps({"final_note":payload.final_note}),payload.final_note,now())); conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",(a["id"],)); audit(conn,user.id,"DOCTOR_APPROVED_NOTE","consultation",cid)
        draft=ai_service.generate("consultation_draft",{"notes":payload.doctor_notes}); missing_ai=ai_service.generate("missing_information",{"missing":missing})
        return {"id":cid,"status":state,"ai_draft":draft.content,"missing_information":missing_ai.content["missing_items"],"ai":{"draft":draft.model_dump(),"missing":missing_ai.model_dump()}}
@app.get("/hospitals/{hospital_id}/capacity")
def hospital_capacity(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return capacity(conn,hospital_id)
@app.get("/hospitals/{hospital_id}/departments")
def department_capacity(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return rows(conn.execute("SELECT d.id,d.name,COUNT(b.id) total_beds,SUM(CASE WHEN b.status='OCCUPIED' THEN 1 ELSE 0 END) occupied,SUM(CASE WHEN b.status='AVAILABLE' THEN 1 ELSE 0 END) available FROM departments d LEFT JOIN beds b ON b.department_id=d.id WHERE d.hospital_id=? GROUP BY d.id,d.name",(hospital_id,)).fetchall())
@app.get("/hospitals/{hospital_id}/beds")
def bed_list(hospital_id:str,department_id:str|None=None,status_filter:str|None=None,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        q="SELECT b.*,d.name department_name,p.id patient_id,u.name patient_name,a.admitted_at,a.expected_discharge_at FROM beds b JOIN departments d ON d.id=b.department_id LEFT JOIN admissions a ON a.bed_id=b.id AND a.status!='DISCHARGED' LEFT JOIN patients p ON p.id=a.patient_id LEFT JOIN users u ON u.id=p.user_id WHERE b.hospital_id=?"; args=(hospital_id,)
        if department_id: q+=" AND b.department_id=?"; args+=(department_id,)
        if status_filter: q+=" AND b.status=?"; args+=(status_filter,)
        return rows(conn.execute(q,args).fetchall())
@app.get("/hospitals/{hospital_id}/flow")
def patient_flow(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        result=rows(conn.execute("SELECT status,COUNT(*) count FROM admissions WHERE hospital_id=? GROUP BY status",(hospital_id,)).fetchall()); blocked=conn.execute("SELECT COUNT(*) FROM admissions a WHERE a.hospital_id=? AND EXISTS(SELECT 1 FROM discharge_blockers b WHERE b.admission_id=a.id AND b.status='OPEN')",(hospital_id,)).fetchone()[0]
        return {"stages":result,"blocked":blocked}
@app.get("/discharge-blockers")
def blockers(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return rows(conn.execute("SELECT b.*,a.patient_id,a.department_id,u.name patient_name,a.expected_discharge_at FROM discharge_blockers b JOIN admissions a ON a.id=b.admission_id JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=p.user_id ORDER BY b.created_at",).fetchall())
@app.get("/hospitals/{hospital_id}/forecast")
def forecast(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        cap=capacity(conn,hospital_id); usable=max(0,cap["expected_discharges"]-cap["delayed_discharges"]); future=cap["available"]+usable-cap["expected_incoming"]; return {"label":"capacity forecast","available_now":cap["available"],"expected_usable_discharges":usable,"expected_incoming":cap["expected_incoming"],"future_capacity":future,"predicted_shortage":max(0,-future),"method":"available + expected usable discharges - expected incoming"}
@app.get("/hospitals/{hospital_id}/recommendations")
def recommendations(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        cap=capacity(conn,hospital_id); data=rows(conn.execute("SELECT t.*,b.blocker_type,a.patient_id FROM tasks t JOIN discharge_blockers b ON b.id=t.blocker_id JOIN admissions a ON a.id=t.admission_id WHERE t.status!='COMPLETED' ORDER BY t.priority_score DESC",).fetchall())
        return [{"task_id":x["id"],"problem":x["blocker_type"],"patient":x["patient_id"],"action":x["title"],"impact":x["impact"],"priority":x["priority"],"why":f"Capacity has only {cap['available']} available beds; resolving this discharge blocker may free one bed."} for x in data]
@app.get("/tasks")
def list_tasks(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        data=rows(conn.execute("SELECT t.*,b.blocker_type,b.created_at blocker_created_at,a.patient_id FROM tasks t JOIN discharge_blockers b ON b.id=t.blocker_id JOIN admissions a ON a.id=t.admission_id WHERE t.status!='COMPLETED' ORDER BY t.priority_score DESC").fetchall()); cap=capacity(conn,"hospital_caspian")
        for t in data: t["priority_score"]=priority_score({"created_at":t["blocker_created_at"],"estimated_minutes":one(conn,"SELECT estimated_minutes FROM discharge_blockers WHERE id=?",(t["blocker_id"],))["estimated_minutes"]},cap)
        return data
@app.post("/tasks/{task_id}/complete")
def complete_task(task_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN","DOCTOR"))):
    with db() as conn:
        t=one(conn,"SELECT * FROM tasks WHERE id=?",(task_id,));
        if not t: raise HTTPException(404,"Task not found")
        conn.execute("UPDATE tasks SET status='COMPLETED',completed_at=? WHERE id=?",(now(),task_id)); conn.execute("UPDATE discharge_blockers SET status='RESOLVED',resolved_at=? WHERE id=?",(now(),t["blocker_id"])); unresolved=conn.execute("SELECT COUNT(*) FROM discharge_blockers WHERE admission_id=? AND status='OPEN'",(t["admission_id"],)).fetchone()[0]
        if unresolved==0: conn.execute("UPDATE admissions SET status='READY_FOR_DISCHARGE' WHERE id=?",(t["admission_id"],))
        notify(conn,role="HOSPITAL_ADMIN",kind="SUCCESS",message=f"Task completed: {t['title']}",related_type="task",related_id=task_id); audit(conn,user.id,"HOSPITAL_TASK_COMPLETED","task",task_id); return {"task_status":"COMPLETED","admission_status":"READY_FOR_DISCHARGE" if unresolved==0 else "BLOCKED"}
@app.post("/admissions/{admission_id}/discharge")
def discharge(admission_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM admissions WHERE id=?",(admission_id,)); blockers=conn.execute("SELECT COUNT(*) FROM discharge_blockers WHERE admission_id=? AND status='OPEN'",(admission_id,)).fetchone()[0]
        if not a or blockers or a["status"] not in ("READY_FOR_DISCHARGE","ACTIVE"): raise HTTPException(409,"Admission is not ready for discharge")
        conn.execute("UPDATE admissions SET status='DISCHARGED' WHERE id=?",(admission_id,)); conn.execute("UPDATE beds SET status='CLEANING' WHERE id=?",(a["bed_id"],)); audit(conn,user.id,"PATIENT_DISCHARGED","admission",admission_id); return {"status":"DISCHARGED","bed_id":a["bed_id"],"bed_status":"CLEANING"}
@app.post("/beds/{bed_id}/complete-cleaning")
def complete_cleaning(bed_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        conn.execute("UPDATE beds SET status='AVAILABLE' WHERE id=? AND status='CLEANING'",(bed_id,)); audit(conn,user.id,"BED_CLEANING_COMPLETED","bed",bed_id); return {"bed_id":bed_id,"status":"AVAILABLE"}
@app.post("/post-discharge/{patient_id}",status_code=201)
def checkin(patient_id:str,payload:CheckinIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        conn.execute("INSERT INTO checkins VALUES(?,?,?,?,?,?,?,?,?)",(uid("checkin"),patient_id,None,date.today().isoformat(),payload.pain_score,payload.temperature,int(payload.medication_taken),payload.symptoms,payload.notes)); history=rows(conn.execute("SELECT * FROM checkins WHERE patient_id=? ORDER BY checkin_date DESC LIMIT 3",(patient_id,)).fetchall()); worsening=len(history)>=2 and (history[0]["pain_score"]>history[-1]["pain_score"] or history[0]["temperature"]>=38)
        if worsening: notify(conn,role="DOCTOR",kind="WARNING",message="Patient post-discharge trend requires review.",related_type="patient",related_id=patient_id)
        return {"trend":"worsening" if worsening else "stable","requires_review":worsening}
@app.post("/cv-events",status_code=201)
def cv_event(payload:CVEventIn,user:DemoUser=Depends(require("HOSPITAL_ADMIN","DOCTOR"))):
    with db() as conn:
        occurred=(payload.timestamp or datetime.now(timezone.utc)).isoformat(); recent=one(conn,"SELECT id FROM cv_events WHERE room_id=? AND event_type=? AND occurred_at>? ORDER BY occurred_at DESC",(payload.room_id,payload.event_type,(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()))
        if recent: return {"id":recent["id"],"status":"deduplicated","notification_created":False}
        eid=uid("cv"); conn.execute("INSERT INTO cv_events VALUES(?,?,?,?,?,?)",(eid,payload.room_id,payload.event_type,payload.severity,payload.confidence,occurred)); conn.execute("INSERT INTO safety_event_details VALUES(?,?,?,?,?,?,?,?)",(eid,payload.patient_state,payload.previous_state,"ACTIVE",None,None,None,json.dumps(payload.metadata))); notify(conn,role="HOSPITAL_ADMIN",kind="CRITICAL",message=f"High fall risk — Room {payload.room_id}: patient attempting to stand without assistance.",related_type="cv_event",related_id=eid); audit(conn,user.id,"CV_EVENT_CREATED","cv_event",eid,{"room_id":payload.room_id,"state":payload.patient_state}); return {"id":eid,"status":"ACTIVE","notification_created":True}
@app.get("/notifications")
def notifications(unread_only:bool=False,kind:str|None=None,user:DemoUser=Depends(current_user)):
    with db() as conn:
        sql="SELECT * FROM notifications WHERE (user_id=? OR role=?)"; args=(user.id,user.role)
        if unread_only: sql+=" AND read_at IS NULL"
        if kind: sql+=" AND type=?"; args+=(kind,)
        return rows(conn.execute(sql+" ORDER BY created_at DESC",args).fetchall())
@app.get("/notifications/unread-count")
def unread_count(user:DemoUser=Depends(current_user)):
    with db() as conn:return {"count":conn.execute("SELECT COUNT(*) FROM notifications WHERE (user_id=? OR role=?) AND read_at IS NULL",(user.id,user.role)).fetchone()[0]}
@app.post("/notifications/read")
def mark_read(payload:ReadIn,user:DemoUser=Depends(current_user)):
    with db() as conn:
        if payload.ids: conn.executemany("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR role=?)",[(now(),item,user.id,user.role) for item in payload.ids])
        else: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=? OR role=?",(now(),user.id,user.role))
        return {"status":"ok"}
@app.patch("/notifications/{notification_id}/read")
def mark_one_read(notification_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn: conn.execute("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR role=?)",(now(),notification_id,user.id,user.role)); return {"id":notification_id,"status":"read"}
@app.patch("/notifications/read-all")
def mark_all_read(user:DemoUser=Depends(current_user)):
    with db() as conn: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=? OR role=?",(now(),user.id,user.role)); return {"status":"ok"}
@app.get("/safety/events")
def safety_events(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return rows(conn.execute("SELECT e.*,d.patient_state,d.previous_state,d.status,d.acknowledged_at,d.resolved_at FROM cv_events e LEFT JOIN safety_event_details d ON d.event_id=e.id ORDER BY e.occurred_at DESC",).fetchall())
@app.patch("/cv-events/{event_id}/acknowledge")
def acknowledge_event(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        conn.execute("UPDATE safety_event_details SET status='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=? WHERE event_id=?",(now(),user.id,event_id)); audit(conn,user.id,"CV_EVENT_ACKNOWLEDGED","cv_event",event_id); return {"id":event_id,"status":"ACKNOWLEDGED"}
@app.post("/cv-events/{event_id}/send-nurse")
def send_nurse(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        event=one(conn,"SELECT * FROM cv_events WHERE id=?",(event_id,));
        if not event: raise HTTPException(404,"Safety event not found")
        task_id=uid("safety_task"); conn.execute("INSERT INTO safety_tasks VALUES(?,?,?,?,?,?,?,?,?)",(task_id,event_id,event["room_id"],f"Assist Patient — Room {event['room_id']}","NURSE","CRITICAL","PENDING",now(),None)); notify(conn,role="HOSPITAL_ADMIN",kind="TASK",message=f"Nurse assistance task created for Room {event['room_id']}.",related_type="safety_task",related_id=task_id); audit(conn,user.id,"NURSE_TASK_CREATED","safety_task",task_id); return {"id":task_id,"status":"PENDING"}
@app.patch("/cv-events/{event_id}/resolve")
def resolve_event(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        conn.execute("UPDATE safety_event_details SET status='RESOLVED',resolved_at=? WHERE event_id=?",(now(),event_id)); audit(conn,user.id,"CV_EVENT_RESOLVED","cv_event",event_id); return {"id":event_id,"status":"RESOLVED"}
@app.post("/demo/reset")
def reset_demo(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    if DB_PATH.exists(): DB_PATH.unlink()
    seed(); return {"status":"reset","message":"Demo data restored."}
@app.get("/audit")
def audits(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return rows(conn.execute("SELECT * FROM audit_events ORDER BY created_at DESC",).fetchall())
@app.get("/ai/lab-explanation/{patient_id}")
def ai_explain(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        data=trends(conn,patient_id); target=next((x for x in data if x["metric"]=="HbA1c"),data[0] if data else None)
        if not target: raise HTTPException(404,"No trends available")
        result=ai_service.generate("lab_explanation",{"trend":target}); return {"data":target,"ai":result.model_dump()}
@app.post("/ai/specialty-recommendation")
def ai_specialty(payload:AITextIn,user:DemoUser=Depends(current_user)):
    with db() as conn:
        data=trends(conn,payload.patient_id or "patient_hasan"); deterministic=specialty_for(data); result=ai_service.generate("specialty",{"specialty":deterministic["suggested_specialty"],"reason":deterministic["reason"]}); return {"deterministic":deterministic,"ai":result.model_dump()}
@app.post("/ai/record-conflict-explanation")
def ai_conflict(payload:AITextIn,user:DemoUser=Depends(current_user)):
    with db() as conn:
        found=conflicts(conn,payload.patient_id or "patient_hasan"); return {"conflicts":found,"ai":ai_service.generate("record_conflict",{"conflicts":found}).model_dump()}
@app.post("/ai/post-discharge-summary")
def ai_post_discharge(payload:AITextIn,user:DemoUser=Depends(current_user)):
    return {"ai":ai_service.generate("post_discharge",{}).model_dump()}
@app.post("/ai/hospital-recommendation")
def ai_hospital(payload:AITextIn,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        task=one(conn,"SELECT * FROM tasks WHERE id=?",(payload.task_id or "task_104",));
        if not task: raise HTTPException(404,"Task not found")
        return {"ai":ai_service.generate("hospital_recommendation",{"title":task["title"],"reason":"The patient is discharge-ready and capacity is constrained.","impact":task["impact"]}).model_dump()}
