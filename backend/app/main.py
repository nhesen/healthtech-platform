from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict,deque
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .ai import ai_service
from .database import DATABASE_KIND, DB_PATH, connect
from .demo_seed import DEMO_VERSION, demo_readiness, reset_demo_data
from .documents import ALLOWED, classify, extract_text, file_hash, parse_lab

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or ROOT / "uploads"); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AVERAGE_CONSULTATION_MINUTES = 15
RATE_BUCKETS:dict[str,deque[float]]=defaultdict(deque)

class Role(str,Enum):
    PATIENT="PATIENT"
    DOCTOR="DOCTOR"
    HOSPITAL_ADMIN="HOSPITAL_ADMIN"
class ClinicalCategory(str,Enum):
    LAB_RESULTS="LAB_RESULTS"
    MEDICATIONS="MEDICATIONS"
    DIAGNOSES="DIAGNOSES"
    DOCTOR_NOTES="DOCTOR_NOTES"
    MENTAL_HEALTH="MENTAL_HEALTH"
    DERMATOLOGY="DERMATOLOGY"
    DISCHARGE_RECORDS="DISCHARGE_RECORDS"

FIN_LENGTH=7
DEMO_FIN_DIRECTORY:dict[str,tuple[str,str]]={"1AZ0001":("patient@demo.az","PATIENT"),"2AZ0002":("doctor@demo.az","DOCTOR"),"3AZ0003":("admin@demo.az","HOSPITAL_ADMIN")}

def demo_enabled()->bool:
    return os.getenv("DEMO_MODE","true").lower() in {"1","true","yes"}
def enforce_rate(key:str,limit:int,window_seconds:int)->None:
    current=time.monotonic();bucket=RATE_BUCKETS[key]
    while bucket and current-bucket[0]>window_seconds:bucket.popleft()
    if len(bucket)>=limit: raise HTTPException(429,"Too many requests. Please try again shortly.")
    bucket.append(current)


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(items: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(item) for item in items]


def one(conn: sqlite3.Connection, query: str, args: tuple = ()) -> dict[str, Any] | None:
    value = conn.execute(query, args).fetchone()
    return dict(value) if value else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK(role IN ('PATIENT','DOCTOR','HOSPITAL_ADMIN')), profile_json TEXT DEFAULT '{}', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hospitals (id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, emergency_waiting INTEGER DEFAULT 0, expected_incoming INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS insurance_plans (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS insurance_coverage (plan_id TEXT NOT NULL, service TEXT NOT NULL, coverage_percent INTEGER NOT NULL CHECK(coverage_percent>=0 AND coverage_percent<=100), PRIMARY KEY(plan_id,service), FOREIGN KEY(plan_id) REFERENCES insurance_plans(id));
CREATE TABLE IF NOT EXISTS departments (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, name TEXT NOT NULL, FOREIGN KEY(hospital_id) REFERENCES hospitals(id));
CREATE TABLE IF NOT EXISTS doctors (id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL, hospital_id TEXT NOT NULL, specialty TEXT NOT NULL, experience_years INTEGER NOT NULL, rating REAL NOT NULL, price REAL NOT NULL, accepted_plans TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS patients (id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL, dob TEXT, gender TEXT, phone TEXT, blood_type TEXT, emergency_contact TEXT, insurance_plan TEXT, allergies_json TEXT DEFAULT '[]', conditions_json TEXT DEFAULT '[]', medications_json TEXT DEFAULT '[]', FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS medical_records (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, record_date TEXT NOT NULL, hospital_id TEXT, doctor_id TEXT, category TEXT NOT NULL, content_json TEXT NOT NULL, raw_text TEXT, created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id));
CREATE TABLE IF NOT EXISTS lab_results (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, reference_range TEXT, result_date TEXT NOT NULL, record_id TEXT, FOREIGN KEY(patient_id) REFERENCES patients(id));
CREATE TABLE IF NOT EXISTS availability (id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY(doctor_id) REFERENCES doctors(id));
CREATE TABLE IF NOT EXISTS appointments (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, slot_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('SCHEDULED','CHECKED_IN','WAITING','IN_PROGRESS','COMPLETED','CANCELLED')), reason TEXT, cost_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(doctor_id) REFERENCES doctors(id), FOREIGN KEY(slot_id) REFERENCES availability(id));
CREATE TABLE IF NOT EXISTS consents (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, categories_json TEXT NOT NULL, starts_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED')), created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(doctor_id) REFERENCES doctors(id));
CREATE TABLE IF NOT EXISTS consultations (id TEXT PRIMARY KEY, appointment_id TEXT NOT NULL, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, transcript TEXT, doctor_notes TEXT, ai_draft TEXT, final_note TEXT, status TEXT NOT NULL, started_at TEXT, completed_at TEXT);
CREATE TABLE IF NOT EXISTS beds (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, department_id TEXT NOT NULL, room TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('AVAILABLE','OCCUPIED','CLEANING','RESERVED','OUT_OF_SERVICE')), FOREIGN KEY(hospital_id) REFERENCES hospitals(id), FOREIGN KEY(department_id) REFERENCES departments(id));
CREATE TABLE IF NOT EXISTS admissions (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, hospital_id TEXT NOT NULL, department_id TEXT NOT NULL, bed_id TEXT NOT NULL, admitted_at TEXT NOT NULL, expected_discharge_at TEXT, clinical_ready INTEGER DEFAULT 0 CHECK(clinical_ready IN (0,1)), status TEXT NOT NULL CHECK(status IN ('ACTIVE','READY_FOR_DISCHARGE','DISCHARGED')), FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(hospital_id) REFERENCES hospitals(id), FOREIGN KEY(department_id) REFERENCES departments(id), FOREIGN KEY(bed_id) REFERENCES beds(id));
CREATE TABLE IF NOT EXISTS discharge_blockers (id TEXT PRIMARY KEY, admission_id TEXT NOT NULL, blocker_type TEXT NOT NULL CHECK(blocker_type IN ('LAB_REVIEW_PENDING','PHARMACY_PENDING','TRANSPORT_PENDING','DOCTOR_APPROVAL_PENDING','DOCUMENTATION_PENDING')), responsible_role TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('OPEN','RESOLVED')), estimated_minutes INTEGER NOT NULL CHECK(estimated_minutes>=0), created_at TEXT NOT NULL, resolved_at TEXT, FOREIGN KEY(admission_id) REFERENCES admissions(id));
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, admission_id TEXT NOT NULL, blocker_id TEXT NOT NULL, assigned_role TEXT NOT NULL, priority TEXT NOT NULL CHECK(priority IN ('LOW','MEDIUM','HIGH','CRITICAL')), priority_score REAL NOT NULL CHECK(priority_score>=0 AND priority_score<=100), status TEXT NOT NULL CHECK(status IN ('PENDING','IN_PROGRESS','COMPLETED')), impact TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, FOREIGN KEY(admission_id) REFERENCES admissions(id), FOREIGN KEY(blocker_id) REFERENCES discharge_blockers(id));
CREATE TABLE IF NOT EXISTS notifications (id TEXT PRIMARY KEY, user_id TEXT, role TEXT, hospital_id TEXT, type TEXT NOT NULL, message TEXT NOT NULL, related_type TEXT, related_id TEXT, read_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkins (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, discharge_id TEXT, checkin_date TEXT NOT NULL, pain_score INTEGER NOT NULL, temperature REAL NOT NULL, medication_taken INTEGER NOT NULL, symptoms TEXT, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cv_events (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, room_id TEXT NOT NULL, event_type TEXT NOT NULL, severity TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence>=0 AND confidence<=1), occurred_at TEXT NOT NULL, FOREIGN KEY(hospital_id) REFERENCES hospitals(id));
CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, hospital_id TEXT NOT NULL, department_id TEXT NOT NULL, safety_status TEXT NOT NULL CHECK(safety_status IN ('STABLE','HIGH_FALL_RISK')), patient_context_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(hospital_id) REFERENCES hospitals(id), FOREIGN KEY(department_id) REFERENCES departments(id));
CREATE TABLE IF NOT EXISTS safety_event_details (event_id TEXT PRIMARY KEY, patient_state TEXT, previous_state TEXT, status TEXT NOT NULL, acknowledged_at TEXT, acknowledged_by TEXT, resolved_at TEXT, metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS safety_tasks (id TEXT PRIMARY KEY, event_id TEXT NOT NULL, room_id TEXT NOT NULL, title TEXT NOT NULL, assigned_role TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, actor_id TEXT, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS medical_documents (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, uploaded_by TEXT NOT NULL, filename TEXT NOT NULL, mime_type TEXT NOT NULL, size INTEGER NOT NULL, storage_path TEXT NOT NULL, file_hash TEXT NOT NULL, document_type TEXT NOT NULL, processing_status TEXT NOT NULL, raw_text TEXT, extraction_json TEXT NOT NULL, confirmed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(patient_id,file_hash));
CREATE TABLE IF NOT EXISTS demo_seed_versions (key TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_records_patient_date ON medical_records(patient_id,record_date);
CREATE INDEX IF NOT EXISTS idx_labs_patient_metric_date ON lab_results(patient_id,metric,result_date);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_status ON appointments(patient_id,status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_active_slot ON appointments(slot_id) WHERE status!='CANCELLED';
CREATE INDEX IF NOT EXISTS idx_consents_patient_doctor ON consents(patient_id,doctor_id,status,expires_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id,read_at);
CREATE INDEX IF NOT EXISTS idx_notifications_role_read ON notifications(role,read_at);
CREATE INDEX IF NOT EXISTS idx_cv_room_time ON cv_events(room_id,occurred_at);
"""


def now() -> str: return datetime.now(timezone.utc).isoformat()
def uid(prefix: str) -> str: return f"{prefix}_{uuid4().hex[:12]}"
def audit(conn, actor, event, kind, entity, details=None):
    conn.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)", (uid("audit"), actor, event, kind, entity, json.dumps(details or {}), now()))
def notify(conn, *, user_id=None, role=None, hospital_id=None, kind="INFO", message: str, related_type=None, related_id=None):
    conn.execute("INSERT INTO notifications (id,user_id,role,hospital_id,type,message,related_type,related_id,read_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (uid("note"), user_id, role, hospital_id, kind, message, related_type, related_id, None, now()))

def migrate(conn:sqlite3.Connection)->None:
    """Apply idempotent compatibility migrations after the baseline schema."""
    if DATABASE_KIND == "postgresql":
        conn.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS hospital_id TEXT")
        conn.execute("ALTER TABLE cv_events ADD COLUMN IF NOT EXISTS hospital_id TEXT NOT NULL DEFAULT 'hospital_caspian'")
        conn.execute("ALTER TABLE checkins ADD COLUMN IF NOT EXISTS created_at TEXT")
        conn.execute("UPDATE users SET profile_json=? WHERE id='user_admin' AND profile_json='{}'",(json.dumps({"hospital_id":"hospital_caspian"}),))
        return
    appointment_sql=(conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='appointments'").fetchone() or [""])[0] or ""
    if "slot_id TEXT NOT NULL UNIQUE" in appointment_sql:
        conn.execute("DROP INDEX IF EXISTS idx_appointments_active_slot")
        conn.execute("""CREATE TABLE appointments_new (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, slot_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('SCHEDULED','CHECKED_IN','WAITING','IN_PROGRESS','COMPLETED','CANCELLED')), reason TEXT, cost_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(doctor_id) REFERENCES doctors(id), FOREIGN KEY(slot_id) REFERENCES availability(id))""")
        conn.execute("INSERT INTO appointments_new SELECT * FROM appointments")
        conn.execute("DROP TABLE appointments")
        conn.execute("ALTER TABLE appointments_new RENAME TO appointments")
        conn.execute("CREATE INDEX idx_appointments_patient_status ON appointments(patient_id,status)")
        conn.execute("CREATE UNIQUE INDEX idx_appointments_active_slot ON appointments(slot_id) WHERE status!='CANCELLED'")
    notification_columns={x[1] for x in conn.execute("PRAGMA table_info(notifications)").fetchall()}
    if "hospital_id" not in notification_columns: conn.execute("ALTER TABLE notifications ADD COLUMN hospital_id TEXT")
    cv_columns={x[1] for x in conn.execute("PRAGMA table_info(cv_events)").fetchall()}
    if "hospital_id" not in cv_columns: conn.execute("ALTER TABLE cv_events ADD COLUMN hospital_id TEXT NOT NULL DEFAULT 'hospital_caspian'")
    checkin_columns={x[1] for x in conn.execute("PRAGMA table_info(checkins)").fetchall()}
    if "created_at" not in checkin_columns: conn.execute("ALTER TABLE checkins ADD COLUMN created_at TEXT")
    conn.execute("UPDATE users SET profile_json=? WHERE id='user_admin' AND profile_json='{}'",(json.dumps({"hospital_id":"hospital_caspian"}),))


def _remove_demo_uploads(paths:list[str])->None:
    for value in paths:
        try:
            path=Path(value).resolve()
            if path.parent==UPLOAD_DIR.resolve() and path.exists():path.unlink()
        except OSError: pass

def seed() -> None:
    paths:list[str]=[]
    with db() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        version=conn.execute("SELECT version FROM demo_seed_versions WHERE key='master'").fetchone()
        if demo_enabled() and (not version or version["version"]<DEMO_VERSION): paths=reset_demo_data(conn)
    _remove_demo_uploads(paths)


class DemoUser(BaseModel): id:str; name:str; email:str; role:Role
def current_user(x_demo_user:str|None=Header(None)) -> DemoUser:
    if not x_demo_user: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Authentication required")
    if not demo_enabled(): raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Demo authentication is disabled")
    with db() as conn:
        user=one(conn,"SELECT id,name,email,role FROM users WHERE email=?",(x_demo_user,))
    if not user: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Invalid or expired demo session")
    return DemoUser(**user)
def require(*roles):
    def dep(user: DemoUser = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,"Insufficient role")
        return user
    return dep
def hospital_scope(conn:sqlite3.Connection,user:DemoUser)->str:
    if user.role==Role.HOSPITAL_ADMIN:
        profile=one(conn,"SELECT profile_json FROM users WHERE id=?",(user.id,))
        hospital_id=json.loads(profile["profile_json"] or "{}").get("hospital_id") if profile else None
    elif user.role==Role.DOCTOR:
        doctor=one(conn,"SELECT hospital_id FROM doctors WHERE user_id=?",(user.id,));hospital_id=doctor["hospital_id"] if doctor else None
    else: hospital_id=None
    if not hospital_id: raise HTTPException(403,"No hospital scope is assigned")
    return hospital_id
def enforce_hospital(conn:sqlite3.Connection,user:DemoUser,hospital_id:str)->None:
    if hospital_scope(conn,user)!=hospital_id: raise HTTPException(403,"Resource belongs to another hospital")
def cv_principal(x_demo_user:str|None=Header(None),x_cv_service_key:str|None=Header(None))->DemoUser:
    expected=os.getenv("CV_SERVICE_TOKEN","")
    if expected and x_cv_service_key and secrets.compare_digest(expected,x_cv_service_key):
        return DemoUser(id="cv_service",name="CV Service",email="cv-service@internal",role=Role.HOSPITAL_ADMIN)
    if demo_enabled() and x_demo_user:
        user=current_user(x_demo_user)
        if user.role in {Role.HOSPITAL_ADMIN,Role.DOCTOR}: return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Valid CV service credentials are required")

def insurance(conn:sqlite3.Connection,plan: str, specialty: str, price: float) -> dict:
    plan_row=one(conn,"SELECT name FROM insurance_plans WHERE id=?",(plan,))
    coverage_row=one(conn,"SELECT coverage_percent FROM insurance_coverage WHERE plan_id=? AND service=?",(plan,specialty))
    percent=coverage_row["coverage_percent"] if coverage_row else 40; paid=round(price*percent/100,2)
    return {"plan":plan,"plan_name":plan_row["name"] if plan_row else plan,"service":specialty,"service_price":price,"coverage_percent":percent,"insurance_payment":paid,"patient_payment":round(price-paid,2)}
def active_consent(conn, patient_id: str, doctor_id: str) -> list[str]:
    c=one(conn,"SELECT categories_json FROM consents WHERE patient_id=? AND doctor_id=? AND status='ACTIVE' AND starts_at<=? AND expires_at>? AND revoked_at IS NULL ORDER BY created_at DESC",(patient_id,doctor_id,now(),now()))
    return json.loads(c["categories_json"]) if c else []
def doctor_patient_access(conn:sqlite3.Connection,patient_id:str,user:DemoUser)->tuple[dict[str,Any],list[str]]:
    doctor=one(conn,"SELECT * FROM doctors WHERE user_id=?",(user.id,))
    if not doctor: raise HTTPException(403,"Doctor profile unavailable")
    relationship=one(conn,"SELECT id FROM appointments WHERE patient_id=? AND doctor_id=? AND status NOT IN ('CANCELLED')",(patient_id,doctor["id"]))
    if not relationship: raise HTTPException(403,"An appointment relationship is required")
    allowed=active_consent(conn,patient_id,doctor["id"])
    if not allowed: raise HTTPException(403,"Active patient consent is required")
    return doctor,allowed
def clinical_access(conn: sqlite3.Connection, patient_id: str, user: DemoUser, categories: tuple[str, ...] = ()) -> list[str]:
    """Enforce patient ownership and category-scoped doctor consent; admins have no clinical access."""
    patient_row=one(conn,"SELECT user_id FROM patients WHERE id=?",(patient_id,))
    if not patient_row: raise HTTPException(404,"Patient not found")
    if user.role=="PATIENT":
        if patient_row["user_id"]!=user.id: raise HTTPException(403,"Only your clinical data is available")
        return list(categories)
    if user.role=="DOCTOR":
        _,allowed=doctor_patient_access(conn,patient_id,user)
        if categories and not all(category in allowed for category in categories):
            raise HTTPException(403,"Active consent for this clinical category is required")
        if not categories and not allowed: raise HTTPException(403,"Active patient consent is required")
        return allowed
    raise HTTPException(403,"Hospital administrators cannot access full clinical records")
def trends(conn, patient_id: str) -> list[dict]:
    result=[]
    for metric in rows(conn.execute("SELECT DISTINCT metric FROM lab_results WHERE patient_id=?",(patient_id,)).fetchall()):
        values=rows(conn.execute("SELECT value,result_date,unit FROM lab_results WHERE patient_id=? AND metric=? ORDER BY result_date",(patient_id,metric["metric"])).fetchall())
        if not values: continue
        current=values[-1]; previous=values[-2] if len(values)>1 else None; change=round(current["value"]-previous["value"],2) if previous else 0
        result.append({"metric":metric["metric"],"current":current["value"],"previous":previous["value"] if previous else None,"change":change,"percent_change":round(change/previous["value"]*100,1) if previous and previous["value"] else None,"trend":"increasing" if change>0 else "decreasing" if change<0 else "stable","history":values})
    return result
def conflicts(conn, patient_id: str, allowed_categories:list[str]|None=None) -> list[dict]:
    allergy=one(conn,"SELECT allergies_json FROM patients WHERE id=?",(patient_id,))
    if allowed_categories is not None:
        if "DIAGNOSES" not in allowed_categories:return []
        if not allowed_categories:return []
        placeholders=",".join("?"*len(allowed_categories)); records=rows(conn.execute(f"SELECT id,title,record_date,category,raw_text,content_json FROM medical_records WHERE patient_id=? AND category IN ({placeholders})",(patient_id,*allowed_categories)).fetchall())
    else: records=rows(conn.execute("SELECT id,title,record_date,category,raw_text,content_json FROM medical_records WHERE patient_id=?",(patient_id,)).fetchall())
    if allergy and json.loads(allergy["allergies_json"]) and any("No known allergies" in (r["raw_text"] or "") for r in records):
        return [{"type":"record_conflict","field":"allergies","severity":"requires_review","message":"Penicillin allergy conflicts with a later 'No known allergies' record.","records":records}]
    return []
def specialty_for(trend_data: list[dict]) -> dict:
    abnormal=[t for t in trend_data if t["metric"] in {"HbA1c","Glucose"} and t["trend"]=="increasing"]
    return {"suggested_specialty":"Endocrinology","reason":"Recent HbA1c or glucose measurements are increasing. This is a navigation suggestion, not a diagnosis."} if abnormal else {"suggested_specialty":"Internal Medicine","reason":"A general clinical review may be useful."}
def capacity(conn,hospital_id: str) -> dict:
    states=rows(conn.execute("SELECT status,COUNT(*) count FROM beds WHERE hospital_id=? GROUP BY status",(hospital_id,)).fetchall()); counts={r["status"]:r["count"] for r in states}; expected=conn.execute("SELECT COUNT(*) AS count FROM admissions WHERE hospital_id=? AND status IN ('ACTIVE','READY_FOR_DISCHARGE') AND clinical_ready=1",(hospital_id,)).fetchone()["count"]; blocked=conn.execute("SELECT COUNT(*) AS count FROM discharge_blockers b JOIN admissions a ON a.id=b.admission_id WHERE a.hospital_id=? AND b.status='OPEN'",(hospital_id,)).fetchone()["count"]; h=one(conn,"SELECT emergency_waiting,expected_incoming FROM hospitals WHERE id=?",(hospital_id,))
    return {"total_beds":sum(counts.values()),"occupied":counts.get("OCCUPIED",0),"available":counts.get("AVAILABLE",0),"cleaning":counts.get("CLEANING",0),"expected_discharges":expected,"delayed_discharges":blocked,"emergency_waiting":h["emergency_waiting"],"expected_incoming":h["expected_incoming"]}
def priority_score(blocker: dict, cap: dict) -> float:
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(blocker["created_at"])).total_seconds()/60
    return round(min(100,35 + min(age,180)/6 + (20 if cap["available"]<10 else 0) + (15 if blocker["estimated_minutes"]<=40 else 5)),1)


@asynccontextmanager
async def lifespan(_:FastAPI):
    seed()
    yield

app=FastAPI(title="HealthTech Backbone",version="0.1.0",lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS","http://localhost:3000,http://localhost:8081").split(",") if x.strip()],
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=False,
    allow_methods=["GET","POST","PATCH","OPTIONS"],
    allow_headers=["Authorization","Content-Type","X-Demo-User","X-CV-Service-Key"],
)
@app.middleware("http")
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store" if request.url.path.startswith(("/patients","/documents","/consents","/notifications","/doctors/patients")) else response.headers.get("Cache-Control","no-cache")
    return response

class AppointmentIn(BaseModel): doctor_id:str=Field(min_length=3,max_length=80); slot_id:str=Field(min_length=3,max_length=80); reason:str=Field("Endocrinology consultation",min_length=2,max_length=300)
class RescheduleIn(BaseModel): slot_id:str
class AppointmentStatusIn(BaseModel): status:Literal["SCHEDULED","CHECKED_IN","WAITING","IN_PROGRESS","COMPLETED","CANCELLED"]
class ConsentIn(BaseModel): doctor_id:str; categories:list[ClinicalCategory]=Field(min_length=1,max_length=7); hours:int=Field(24,ge=1,le=168)
class ConsultationIn(BaseModel): appointment_id:str; transcript:str=""; doctor_notes:str=""; final_note:str|None=None; complete:bool=False
class CheckinIn(BaseModel): pain_score:int=Field(ge=1,le=10); temperature:float=Field(ge=30,le=45); medication_taken:bool; symptoms:str=Field("",max_length=1000); notes:str=Field("",max_length=2000)
class CVEventIn(BaseModel): hospital_id:str="hospital_caspian"; room_id:str=Field(min_length=1,max_length=30); event_type:Literal["FALL_RISK","PATIENT_STANDING","OUT_OF_BED"]="FALL_RISK"; severity:Literal["HIGH","CRITICAL","WARNING","MEDIUM"]="HIGH"; confidence:float=Field(ge=0,le=1); patient_state:Literal["LYING","SITTING","STANDING","UNKNOWN","OUT_OF_BED"]="STANDING"; previous_state:Literal["LYING","SITTING","STANDING","UNKNOWN","OUT_OF_BED"]="SITTING"; timestamp:datetime|None=None; metadata:dict[str,Any]=Field(default_factory=dict)
class ReadIn(BaseModel): ids:list[str]=[]
class AITextIn(BaseModel): patient_id:str|None=None; notes:str=""; missing:list[str]=[]; task_id:str|None=None
class LabResultIn(BaseModel): test_name:str=Field(min_length=1,max_length=100); value:float=Field(ge=-1_000_000,le=1_000_000); unit:str=Field("",max_length=40); reference_text:str=Field("",max_length=100)
class DocumentConfirmIn(BaseModel): results:list[LabResultIn]=Field(default_factory=list,max_length=100); report_date:date|None=None; source_name:str|None=Field(None,max_length=200)
class DocumentReviewIn(BaseModel): results:list[LabResultIn]=Field(max_length=100); report_date:date|None=None; source_name:str|None=Field(None,max_length=200)
class TaskUpdateIn(BaseModel): status:Literal["IN_PROGRESS"]; assigned_role:Literal["DOCTOR","HOSPITAL_ADMIN","NURSE","PHARMACY"]|None=None
class LoginIn(BaseModel): fin:str=Field(min_length=FIN_LENGTH,max_length=FIN_LENGTH,pattern=r"^[0-9A-Za-z]{7}$"); role:Role

@app.get("/health")
def health():
    try:
        with db() as conn: conn.execute("SELECT 1").fetchone()
        return {"status":"ok","database":"connected","demo_mode":demo_enabled()}
    except Exception:
        return JSONResponse(status_code=503,content={"status":"degraded","database":"unavailable","demo_mode":demo_enabled()})
@app.get("/health/demo")
def health_demo(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    if not demo_enabled(): raise HTTPException(404,"Not found")
    with db() as conn:
        result=demo_readiness(conn,ROOT/"demo_documents"/"hasan_lab_report.pdf")
        result.update({"database":"ok","storage":"writable" if os.access(UPLOAD_DIR,os.W_OK) else "unavailable","ai_provider":"live" if os.getenv("AI_PROVIDER","mock").lower()=="openai" and bool(os.getenv("AI_API_KEY")) else "deterministic_fallback","cv_ingestion":"service-token-ready" if os.getenv("CV_SERVICE_TOKEN") else "demo-simulator-ready"})
        return result
@app.get("/auth/me")
def me(user:DemoUser=Depends(current_user)): return user
@app.get("/auth/demo-accounts")
def accounts():
    if not demo_enabled(): raise HTTPException(404,"Not found")
    with db() as conn: return rows(conn.execute("SELECT name,email,role FROM users WHERE email IN ('patient@demo.az','doctor@demo.az','admin@demo.az')").fetchall())
@app.post("/auth/login")
def login(payload:LoginIn):
    """Resolve a synthetic FIN and role to the demo identity used by the X-Demo-User header."""
    if not demo_enabled(): raise HTTPException(404,"Not found")
    fin=payload.fin.strip().upper()
    enforce_rate("login",30,60)
    entry=DEMO_FIN_DIRECTORY.get(fin)
    if not entry or entry[1]!=payload.role.value: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"FIN və ya rol yanlışdır")
    email,_=entry
    with db() as conn:
        user=one(conn,"SELECT id,name,email,role FROM users WHERE email=?",(email,))
        if not user: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"FIN və ya rol yanlışdır")
        audit(conn,user["id"],"DEMO_LOGIN","user",user["id"],{"role":user["role"]})
    return DemoUser(**user)
@app.get("/patients/{patient_id}")
def patient(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        p=one(conn,"SELECT p.*,u.name,u.email FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,))
        allowed=clinical_access(conn,patient_id,user)
        if user.role=="DOCTOR":
            return {"id":p["id"],"name":p["name"],"dob":p["dob"],"gender":p["gender"],"blood_type":p["blood_type"],"allergies_json":p["allergies_json"] if "DIAGNOSES" in allowed else "[]","conditions_json":p["conditions_json"] if "DIAGNOSES" in allowed else "[]","medications_json":p["medications_json"] if "MEDICATIONS" in allowed else "[]"}
        return p
@app.get("/patients/{patient_id}/timeline")
def timeline(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        allowed=clinical_access(conn,patient_id,user)
        if user.role=="DOCTOR":
            placeholders=",".join("?" for _ in allowed)
            return rows(conn.execute(f"SELECT * FROM medical_records WHERE patient_id=? AND category IN ({placeholders}) ORDER BY record_date DESC",(patient_id,*allowed)).fetchall())
        return rows(conn.execute("SELECT * FROM medical_records WHERE patient_id=? ORDER BY record_date DESC",(patient_id,)).fetchall())
@app.get("/patients/{patient_id}/lab-results")
def labs(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        clinical_access(conn,patient_id,user,("LAB_RESULTS",))
        return rows(conn.execute("SELECT * FROM lab_results WHERE patient_id=? ORDER BY result_date DESC",(patient_id,)).fetchall())
def document_access(conn, document:dict, user:DemoUser):
    if user.role=="PATIENT":
        if one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(document["patient_id"],user.id)):return
    if user.role=="DOCTOR":
        _,allowed=doctor_patient_access(conn,document["patient_id"],user)
        if "LAB_RESULTS" in allowed:return
    raise HTTPException(403,"Document access is not authorized")
@app.post("/documents/upload",status_code=201)
async def upload_document(file:UploadFile=File(...),patient_id:str="patient_hasan",user:DemoUser=Depends(current_user)):
    enforce_rate(f"document:{user.id}",20,60)
    extension=Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED or extension not in {".pdf",".png",".jpg",".jpeg"}: raise HTTPException(415,"Please upload a PDF, PNG, or JPG file.")
    data=await file.read(15*1024*1024+1)
    signatures={"application/pdf":data.startswith(b"%PDF"),"image/png":data.startswith(b"\x89PNG\r\n\x1a\n"),"image/jpeg":data.startswith(b"\xff\xd8\xff")}
    if not data or not signatures.get(file.content_type,False): raise HTTPException(422,"File content does not match its declared type.")
    if len(data)>15*1024*1024: raise HTTPException(413,"Maximum file size is 15 MB.")
    with db() as conn:
        if user.role=="PATIENT":
            if not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(patient_id,user.id)):raise HTTPException(403,"Patient mismatch")
        elif user.role=="DOCTOR":
            _,allowed=doctor_patient_access(conn,patient_id,user)
            if "LAB_RESULTS" not in allowed:raise HTTPException(403,"Valid lab-result consent is required")
        else: raise HTTPException(403,"Only patient or authorized doctor can upload")
        digest=file_hash(data); existing=one(conn,"SELECT id FROM medical_documents WHERE patient_id=? AND file_hash=?",(patient_id,digest))
        if existing: raise HTTPException(409,"This document appears to have already been uploaded.")
        did=uid("doc"); safe_name=re.sub(r"[^A-Za-z0-9._-]","_",Path(file.filename or "document").name).lstrip(".") or "document"; target=UPLOAD_DIR/f"{did}_{safe_name}"; target.write_bytes(data); text=extract_text(data,file.content_type or ""); dtype,confidence=classify(text); parsed=parse_lab(text) if dtype=="LAB_REPORT" else {"results":[]}; parsed.update({"document_type":dtype,"confidence":confidence}); state="NEEDS_REVIEW" if parsed["results"] else "UPLOADED"; stamp=now(); conn.execute("INSERT INTO medical_documents (id,patient_id,uploaded_by,filename,mime_type,size,storage_path,file_hash,document_type,processing_status,raw_text,extraction_json,confirmed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(did,patient_id,user.id,safe_name,file.content_type,len(data),str(target),digest,dtype,state,text,json.dumps(parsed),None,stamp,stamp)); notify(conn,user_id=user.id,kind="INFO",message="Document processed. Review extracted information before confirming.",related_type="document",related_id=did); audit(conn,user.id,"DOCUMENT_UPLOADED","document",did,{"type":dtype}); return {"document_id":did,"status":state,"extraction":parsed}
@app.get("/documents")
def documents(patient_id:str="patient_hasan",user:DemoUser=Depends(current_user)):
    with db() as conn:
        clinical_access(conn,patient_id,user,("LAB_RESULTS",))
        return rows(conn.execute("SELECT id,filename,document_type,processing_status,created_at,confirmed_at FROM medical_documents WHERE patient_id=? ORDER BY created_at DESC",(patient_id,)).fetchall())
@app.get("/documents/{document_id}")
def document_detail(document_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        doc=one(conn,"SELECT * FROM medical_documents WHERE id=?",(document_id,));
        if not doc:raise HTTPException(404,"Document not found")
        document_access(conn,doc,user)
        return {key:doc[key] for key in ("id","patient_id","filename","mime_type","size","document_type","processing_status","extraction_json","confirmed_at","created_at","updated_at")}
@app.patch("/documents/{document_id}/review")
def review_document(document_id:str,payload:DocumentReviewIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        doc=one(conn,"SELECT * FROM medical_documents WHERE id=?",(document_id,))
        if not doc: raise HTTPException(404,"Document not found")
        document_access(conn,doc,user)
        if doc["processing_status"]=="CONFIRMED": raise HTTPException(409,"Confirmed documents cannot be edited")
        if payload.report_date and payload.report_date>date.today(): raise HTTPException(422,"Report date cannot be in the future")
        extraction=json.loads(doc["extraction_json"]); extraction.update({"results":[x.model_dump() for x in payload.results],"report_date":payload.report_date.isoformat() if payload.report_date else None,"source_name":payload.source_name})
        conn.execute("UPDATE medical_documents SET extraction_json=?,processing_status='NEEDS_REVIEW',updated_at=? WHERE id=?",(json.dumps(extraction),now(),document_id)); audit(conn,user.id,"DOCUMENT_REVIEWED","document",document_id,{"result_count":len(payload.results)})
        return {"id":document_id,"status":"NEEDS_REVIEW","extraction":extraction}
@app.post("/documents/{document_id}/confirm")
def confirm_document(document_id:str,payload:DocumentConfirmIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        doc=one(conn,"SELECT * FROM medical_documents WHERE id=?",(document_id,));
        if not doc:raise HTTPException(404,"Document not found")
        document_access(conn,doc,user)
        if doc["processing_status"]=="CONFIRMED": raise HTTPException(409,"Document has already been confirmed")
        if payload.report_date and payload.report_date>date.today(): raise HTTPException(422,"Report date cannot be in the future")
        extracted=json.loads(doc["extraction_json"]); results=[x.model_dump() for x in payload.results] or extracted.get("results",[])
        if not results: raise HTTPException(422,"Add at least one reviewed lab result before confirming")
        report_date=payload.report_date.isoformat() if payload.report_date else extracted.get("report_date") or date.today().isoformat(); source=payload.source_name or extracted.get("source_name") or "Uploaded document"; record=uid("record"); conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(record,doc["patient_id"],"LAB_RESULT",doc["filename"],report_date,None,None,"LAB_RESULTS",json.dumps({"source_document_id":document_id,"source":source,"results":results}),doc["raw_text"],now()))
        created_count=0
        for item in results:
            if not item.get("test_name") or item.get("value") is None:continue
            duplicate=one(conn,"SELECT id FROM lab_results WHERE patient_id=? AND metric=? AND value=? AND result_date=?",(doc["patient_id"],item["test_name"],float(item["value"]),report_date))
            if duplicate: continue
            conn.execute("INSERT INTO lab_results (id,patient_id,metric,value,unit,reference_range,result_date,record_id) VALUES(?,?,?,?,?,?,?,?)",(uid("lab"),doc["patient_id"],item["test_name"],float(item["value"]),item.get("unit","") or "",item.get("reference_text","") or "",report_date,record))
            created_count+=1
        conn.execute("UPDATE medical_documents SET processing_status='CONFIRMED',confirmed_at=?,updated_at=? WHERE id=?",(now(),now(),document_id)); notify(conn,user_id=user.id,kind="SUCCESS",message="Lab results added to your health timeline.",related_type="document",related_id=document_id); audit(conn,user.id,"DOCUMENT_CONFIRMED","document",document_id,{"result_count":created_count,"source":source}); return {"status":"CONFIRMED","record_id":record,"results_created":created_count}
@app.get("/patients/{patient_id}/trends")
def lab_trends(patient_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        allowed=clinical_access(conn,patient_id,user,("LAB_RESULTS",)); data=trends(conn,patient_id)
        return {"trends":data,"conflicts":conflicts(conn,patient_id,None if user.role==Role.PATIENT else allowed),"care_navigation":specialty_for(data)}
@app.get("/patients/{patient_id}/overview")
def patient_overview(patient_id:str,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        p=one(conn,"SELECT p.*,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,))
        allowed=clinical_access(conn,patient_id,user)
        upcoming=one(conn,"SELECT a.*,u.name doctor_name,d.specialty,h.name hospital_name,s.starts_at FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id JOIN availability s ON s.id=a.slot_id WHERE a.patient_id=? AND a.status NOT IN ('CANCELLED','COMPLETED') ORDER BY s.starts_at LIMIT 1",(patient_id,))
        records=rows(conn.execute("SELECT type,title,record_date,category FROM medical_records WHERE patient_id=? ORDER BY record_date DESC LIMIT 4",(patient_id,)).fetchall()); plan=one(conn,"SELECT name FROM insurance_plans WHERE id=?",(p["insurance_plan"],))
        return {"patient":{"id":patient_id,"name":p["name"],"insurance_plan":plan["name"] if plan else p["insurance_plan"],"allergies":json.loads(p["allergies_json"]),"conditions":json.loads(p["conditions_json"]),"medications":json.loads(p["medications_json"])},"upcoming_appointment":upcoming,"recent_activity":records,"insight_count":len(conflicts(conn,patient_id))+sum(1 for x in trends(conn,patient_id) if x["trend"]=="increasing")}
@app.get("/patients/{patient_id}/lab-comparison")
def lab_comparison(patient_id:str,from_date:date,to_date:date,user:DemoUser=Depends(current_user)):
    with db() as conn:
        clinical_access(conn,patient_id,user,("LAB_RESULTS",))
        if from_date>to_date: raise HTTPException(422,"from_date must not be after to_date")
        from_value,to_value=from_date.isoformat(),to_date.isoformat(); all_labs=rows(conn.execute("SELECT metric,value,unit,result_date,reference_range FROM lab_results WHERE patient_id=? ORDER BY result_date",(patient_id,)).fetchall()); result=[]
        for metric in sorted({x["metric"] for x in all_labs}):
            series=[x for x in all_labs if x["metric"]==metric]; old=max((x for x in series if x["result_date"]<=from_value),key=lambda x:x["result_date"],default=None); new=max((x for x in series if x["result_date"]<=to_value),key=lambda x:x["result_date"],default=None)
            if old and new: result.append({"metric":metric,"from":old,"to":new,"change":round(new["value"]-old["value"],2),"direction":"up" if new["value"]>old["value"] else "down" if new["value"]<old["value"] else "same"})
        changed=[x["metric"] for x in result if x["change"]]
        return {"from_date":from_value,"to_date":to_value,"metrics":result,"explanation":f"{len(changed)} metrics changed between these tests. This comparison does not provide a diagnosis."}
@app.get("/insurance/plan")
def insurance_plan(patient_id:str,user:DemoUser=Depends(require("PATIENT"))):
    """Coverage percentages the patient's plan applies per service, straight from insurance_coverage."""
    with db() as conn:
        clinical_access(conn,patient_id,user)
        patient=one(conn,"SELECT insurance_plan FROM patients WHERE id=?",(patient_id,))
        if not patient: raise HTTPException(404,"Patient not found")
        plan=patient["insurance_plan"]; plan_row=one(conn,"SELECT name FROM insurance_plans WHERE id=?",(plan,))
        coverage=rows(conn.execute("SELECT service,coverage_percent FROM insurance_coverage WHERE plan_id=? ORDER BY coverage_percent DESC,service",(plan,)).fetchall())
        return {"plan":plan,"plan_name":plan_row["name"] if plan_row else plan,"coverage":coverage}
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
@app.get("/doctors/{doctor_id}")
def doctor_profile(doctor_id:str):
    with db() as conn:
        doctor=one(conn,"SELECT d.*,u.name,h.name hospital_name,h.city FROM doctors d JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id WHERE d.id=?",(doctor_id,))
        if not doctor: raise HTTPException(404,"Doctor not found")
        doctor["accepted_plans"]=doctor["accepted_plans"].split(",")
        doctor["availability"]=rows(conn.execute("SELECT id,starts_at,ends_at,status FROM availability WHERE doctor_id=? ORDER BY starts_at",(doctor_id,)).fetchall())
        return doctor
@app.get("/insurance/estimate")
def insurance_estimate(patient_id:str,doctor_id:str,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        clinical_access(conn,patient_id,user)
        p=one(conn,"SELECT insurance_plan FROM patients WHERE id=?",(patient_id,)); d=one(conn,"SELECT specialty,price FROM doctors WHERE id=?",(doctor_id,))
        if not p or not d: raise HTTPException(404,"Patient or doctor not found")
        return insurance(conn,p["insurance_plan"],d["specialty"],d["price"])
@app.post("/appointments",status_code=201)
def book(payload:AppointmentIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        p=one(conn,"SELECT id,insurance_plan FROM patients WHERE user_id=?",(user.id,)); d=one(conn,"SELECT specialty,price FROM doctors WHERE id=?",(payload.doctor_id,))
        if not p or not d: raise HTTPException(404,"Patient or doctor not found")
        reserved=conn.execute("UPDATE availability SET status='BOOKED' WHERE id=? AND doctor_id=? AND status='AVAILABLE'",(payload.slot_id,payload.doctor_id))
        if reserved.rowcount!=1: raise HTTPException(409,"Slot is no longer available")
        slot=one(conn,"SELECT starts_at FROM availability WHERE id=?",(payload.slot_id,))
        if datetime.fromisoformat(slot["starts_at"])<=datetime.now(timezone.utc): raise HTTPException(409,"Appointment slot must be in the future")
        cost=insurance(conn,p["insurance_plan"],d["specialty"],d["price"]); aid=uid("appt"); conn.execute("INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?)",(aid,p["id"],payload.doctor_id,payload.slot_id,"SCHEDULED",payload.reason,json.dumps(cost),now())); notify(conn,user_id=user.id,kind="SUCCESS",message="Appointment confirmed.",related_type="appointment",related_id=aid); doctor_user=one(conn,"SELECT user_id FROM doctors WHERE id=?",(payload.doctor_id,)); notify(conn,user_id=doctor_user["user_id"],kind="TASK",message="New appointment scheduled.",related_type="appointment",related_id=aid); audit(conn,user.id,"APPOINTMENT_BOOKED","appointment",aid,cost)
        return {"id":aid,"status":"SCHEDULED","cost":cost,"consent_suggested":True}
@app.get("/appointments")
def list_appointments(user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role=="PATIENT": q="SELECT a.*,u.name doctor_name,d.specialty,h.name hospital_name,s.starts_at FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id JOIN availability s ON s.id=a.slot_id WHERE p.user_id=?"; data=rows(conn.execute(q,(user.id,)).fetchall())
        elif user.role=="DOCTOR": data=rows(conn.execute("SELECT a.id,a.patient_id,a.doctor_id,a.slot_id,a.status,a.reason,a.created_at,u.name patient_name,s.starts_at FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=p.user_id JOIN availability s ON s.id=a.slot_id WHERE d.user_id=?",(user.id,)).fetchall())
        else: data=rows(conn.execute("SELECT a.id,a.patient_id,a.doctor_id,a.slot_id,a.status,a.created_at FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE d.hospital_id=?",(hospital_scope(conn,user),)).fetchall())
        return data
@app.patch("/appointments/{appointment_id}/cancel")
def cancel(appointment_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,));
        if not a: raise HTTPException(404,"Appointment not found")
        if user.role=="PATIENT" and not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(a["patient_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        if user.role=="DOCTOR" and not one(conn,"SELECT id FROM doctors WHERE id=? AND user_id=?",(a["doctor_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        if user.role==Role.HOSPITAL_ADMIN: raise HTTPException(403,"Hospital admins cannot cancel clinical appointments")
        if a["status"]=="CANCELLED": return {"status":"CANCELLED"}
        if a["status"] not in {"SCHEDULED","CHECKED_IN","WAITING"}: raise HTTPException(409,f"Appointment cannot be cancelled from {a['status']}")
        conn.execute("UPDATE appointments SET status='CANCELLED' WHERE id=?",(appointment_id,)); conn.execute("UPDATE availability SET status='AVAILABLE' WHERE id=?",(a["slot_id"],)); patient_user=one(conn,"SELECT user_id FROM patients WHERE id=?",(a["patient_id"],)); notify(conn,user_id=patient_user["user_id"],kind="INFO",message="Appointment cancelled.",related_type="appointment",related_id=appointment_id); audit(conn,user.id,"APPOINTMENT_CANCELLED","appointment",appointment_id); return {"status":"CANCELLED"}
@app.patch("/appointments/{appointment_id}/status")
def appointment_status(appointment_id:str,payload:AppointmentStatusIn,user:DemoUser=Depends(require("DOCTOR"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,));
        if not a: raise HTTPException(404,"Appointment not found")
        if user.role=="DOCTOR" and not one(conn,"SELECT id FROM doctors WHERE id=? AND user_id=?",(a["doctor_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        transitions={"SCHEDULED":"CHECKED_IN","CHECKED_IN":"WAITING","WAITING":"IN_PROGRESS","IN_PROGRESS":"COMPLETED"}
        if transitions.get(a["status"])!=payload.status: raise HTTPException(409,f"Invalid appointment transition: {a['status']} to {payload.status}")
        conn.execute("UPDATE appointments SET status=? WHERE id=?",(payload.status,appointment_id)); patient_user=one(conn,"SELECT user_id FROM patients WHERE id=?",(a["patient_id"],));
        if payload.status in ("CHECKED_IN","WAITING","COMPLETED"): notify(conn,user_id=patient_user["user_id"],kind="INFO",message=f"Appointment status updated: {payload.status.replace('_',' ').title()}.",related_type="appointment",related_id=appointment_id)
        audit(conn,user.id,"APPOINTMENT_STATUS_UPDATED","appointment",appointment_id,{"status":payload.status}); return {"id":appointment_id,"status":payload.status}
@app.patch("/appointments/{appointment_id}/reschedule")
def reschedule(appointment_id:str,payload:RescheduleIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(appointment_id,)); slot=one(conn,"SELECT * FROM availability WHERE id=?",(payload.slot_id,))
        if not a or not slot or slot["doctor_id"]!=a["doctor_id"]: raise HTTPException(404,"Appointment or slot not found")
        if not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(a["patient_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        if a["status"]!="SCHEDULED": raise HTTPException(409,"Only scheduled appointments can be rescheduled")
        if slot["status"]!="AVAILABLE": raise HTTPException(409,"Slot is no longer available")
        if datetime.fromisoformat(slot["starts_at"])<=datetime.now(timezone.utc): raise HTTPException(409,"Appointment slot must be in the future")
        if conn.execute("UPDATE availability SET status='BOOKED' WHERE id=? AND status='AVAILABLE'",(payload.slot_id,)).rowcount!=1: raise HTTPException(409,"Slot is no longer available")
        conn.execute("UPDATE appointments SET slot_id=? WHERE id=?",(payload.slot_id,appointment_id)); conn.execute("UPDATE availability SET status='AVAILABLE' WHERE id=?",(a["slot_id"],)); notify(conn,user_id=user.id,kind="INFO",message="Appointment rescheduled.",related_type="appointment",related_id=appointment_id); audit(conn,user.id,"APPOINTMENT_RESCHEDULED","appointment",appointment_id); return {"status":"SCHEDULED","slot_id":payload.slot_id}
@app.get("/appointments/{appointment_id}/queue")
def queue(appointment_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        a=one(conn,"SELECT a.*,s.starts_at FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.id=?",(appointment_id,));
        if not a: raise HTTPException(404,"Appointment not found")
        if user.role=="PATIENT" and not one(conn,"SELECT id FROM patients WHERE id=? AND user_id=?",(a["patient_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        if user.role=="DOCTOR" and not one(conn,"SELECT id FROM doctors WHERE id=? AND user_id=?",(a["doctor_id"],user.id)): raise HTTPException(403,"Appointment unavailable")
        if user.role=="HOSPITAL_ADMIN": raise HTTPException(403,"Queue access is limited to the patient and treating doctor")
        before=conn.execute("SELECT COUNT(*) AS count FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.doctor_id=? AND date(s.starts_at)=date(?) AND s.starts_at<? AND a.status NOT IN ('CANCELLED','COMPLETED')",(a["doctor_id"],a["starts_at"],a["starts_at"])).fetchone()["count"]
        return {"queue_position":before+1,"patients_before":before,"estimated_wait_minutes":before*AVERAGE_CONSULTATION_MINUTES}
@app.post("/demo/queue/advance")
def advance_demo_queue(user:DemoUser=Depends(require("DOCTOR"))):
    if not demo_enabled(): raise HTTPException(404,"Not found")
    with db() as conn:
        doctor=one(conn,"SELECT id FROM doctors WHERE user_id=?",(user.id,))
        target=one(conn,"SELECT a.*,s.starts_at FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.patient_id='patient_hasan' AND a.doctor_id=? AND a.status NOT IN ('CANCELLED','COMPLETED') ORDER BY a.created_at DESC LIMIT 1",(doctor["id"],)) if doctor else None
        if not target: raise HTTPException(409,"Book Hasan's demo appointment before advancing the queue")
        ahead=one(conn,"SELECT a.id FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.doctor_id=? AND date(s.starts_at)=date(?) AND s.starts_at<? AND a.status NOT IN ('CANCELLED','COMPLETED') ORDER BY s.starts_at LIMIT 1",(target["doctor_id"],target["starts_at"],target["starts_at"]))
        if not ahead: raise HTTPException(409,"The demo queue is already at the front")
        conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",(ahead["id"],)); audit(conn,user.id,"DEMO_QUEUE_ADVANCED","appointment",ahead["id"])
        before=conn.execute("SELECT COUNT(*) AS count FROM appointments a JOIN availability s ON s.id=a.slot_id WHERE a.doctor_id=? AND date(s.starts_at)=date(?) AND s.starts_at<? AND a.status NOT IN ('CANCELLED','COMPLETED')",(target["doctor_id"],target["starts_at"],target["starts_at"])).fetchone()["count"]
        return {"advanced_appointment_id":ahead["id"],"queue_position":before+1,"patients_before":before,"estimated_wait_minutes":before*AVERAGE_CONSULTATION_MINUTES}
@app.post("/consents",status_code=201)
def grant_consent(payload:ConsentIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        valid={"LAB_RESULTS","MEDICATIONS","DIAGNOSES","DOCTOR_NOTES","MENTAL_HEALTH","DERMATOLOGY","DISCHARGE_RECORDS"}
        if not payload.categories or any(x not in valid for x in payload.categories): raise HTTPException(422,"Select one or more valid consent categories")
        if not one(conn,"SELECT id FROM doctors WHERE id=?",(payload.doctor_id,)): raise HTTPException(404,"Doctor not found")
        p=one(conn,"SELECT id FROM patients WHERE user_id=?",(user.id,)); cid=uid("consent"); start=datetime.now(timezone.utc); expires=start+timedelta(hours=payload.hours); conn.execute("UPDATE consents SET status='REVOKED',revoked_at=? WHERE patient_id=? AND doctor_id=? AND status='ACTIVE'",(start.isoformat(),p["id"],payload.doctor_id)); conn.execute("INSERT INTO consents VALUES(?,?,?,?,?,?,?,?,?)",(cid,p["id"],payload.doctor_id,json.dumps(sorted(set(payload.categories))),start.isoformat(),expires.isoformat(),None,"ACTIVE",now())); notify(conn,user_id=user.id,kind="SUCCESS",message="Medical record access granted.",related_type="consent",related_id=cid); audit(conn,user.id,"CONSENT_GRANTED","consent",cid,{"categories":payload.categories}); return {"id":cid,"expires_at":expires.isoformat(),"status":"ACTIVE"}
@app.get("/consents")
def list_consents(user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:return rows(conn.execute("SELECT c.*,u.name doctor_name,d.specialty,h.name hospital_name FROM consents c JOIN doctors d ON d.id=c.doctor_id JOIN users u ON u.id=d.user_id JOIN hospitals h ON h.id=d.hospital_id JOIN patients p ON p.id=c.patient_id WHERE p.user_id=? ORDER BY c.created_at DESC",(user.id,)).fetchall())
@app.post("/consents/{consent_id}/revoke")
def revoke_consent(consent_id:str,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        c=one(conn,"SELECT c.* FROM consents c JOIN patients p ON p.id=c.patient_id WHERE c.id=? AND p.user_id=?",(consent_id,user.id))
        if not c: raise HTTPException(404,"Consent not found")
        conn.execute("UPDATE consents SET status='REVOKED',revoked_at=? WHERE id=?",(now(),consent_id)); notify(conn,user_id=user.id,kind="INFO",message="Medical record access revoked.",related_type="consent",related_id=consent_id); audit(conn,user.id,"CONSENT_REVOKED","consent",consent_id); return {"status":"REVOKED"}
@app.get("/privacy-history")
def privacy_history(user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        patient_row=one(conn,"SELECT id FROM patients WHERE user_id=?",(user.id,))
        return rows(conn.execute("SELECT a.id,a.event_type,a.details_json,a.created_at,u.name actor_name,u.role actor_role FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id WHERE a.entity_type='patient' AND a.entity_id=? ORDER BY a.created_at DESC",(patient_row["id"],)).fetchall())
@app.get("/doctors/patients/{patient_id}/brief")
def doctor_brief(patient_id:str,user:DemoUser=Depends(require("DOCTOR"))):
    with db() as conn:
        d,allowed=doctor_patient_access(conn,patient_id,user)
        p=one(conn,"SELECT p.*,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",(patient_id,)); data=trends(conn,patient_id) if "LAB_RESULTS" in allowed else []; relevant=[x for x in data if x["metric"] in ("HbA1c","Glucose")] if d["specialty"]=="Endocrinology" else data; records=rows(conn.execute("SELECT * FROM medical_records WHERE patient_id=? AND category IN (%s) ORDER BY record_date DESC" % ",".join("?"*len(allowed)),(patient_id,*allowed)).fetchall()); audit(conn,user.id,"DOCTOR_VIEWED_RECORD","patient",patient_id,{"categories":allowed})
        visible_conflicts=conflicts(conn,patient_id,allowed) if "LAB_RESULTS" in allowed and "DIAGNOSES" in allowed else []; context={"relevant_metrics":relevant,"medications":json.loads(p["medications_json"]) if "MEDICATIONS" in allowed else [],"allergies":json.loads(p["allergies_json"]) if "DIAGNOSES" in allowed else []}; ai=ai_service.generate("patient_brief",context)
        return {**ai.content,"patient":{"id":patient_id,"name":p["name"],"dob":p["dob"]},"reason_for_visit":"Endocrinology consultation","allowed_categories":allowed,"important_history":[r["title"] for r in records],"relevant_metrics":relevant,"medications":context["medications"],"allergies":context["allergies"],"warnings":visible_conflicts,"ai_warnings":ai.content.get("warnings",[]),"ai":ai.model_dump()}
@app.post("/consultations",status_code=201)
def consultation(payload:ConsultationIn,user:DemoUser=Depends(require("DOCTOR"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM appointments WHERE id=?",(payload.appointment_id,)); d=one(conn,"SELECT id FROM doctors WHERE user_id=?",(user.id,));
        if not a or a["doctor_id"]!=d["id"]: raise HTTPException(403,"Appointment unavailable")
        if "DOCTOR_NOTES" not in active_consent(conn,a["patient_id"],d["id"]): raise HTTPException(403,"Consent for doctor notes is required")
        if payload.complete and a["status"]!="IN_PROGRESS": raise HTTPException(409,"Appointment must be in progress before final approval")
        if a["status"] in {"CANCELLED","COMPLETED"}: raise HTTPException(409,"Consultation is not available for this appointment")
        missing=[]; text=(payload.transcript+" "+payload.doctor_notes).lower()
        if "medication" in text and not any(x in text for x in ["mg","ml","dose","dosage"]): missing.append("Medication dosage not documented")
        if "allergy" in text and not any(x in text for x in ["rash","reaction","anaphyl"]): missing.append("Allergy reaction not documented")
        if "symptom" in text and not any(x in text for x in ["day","week","month","duration"]): missing.append("Symptom duration not documented")
        cid=uid("consult"); state="COMPLETED" if payload.complete and payload.final_note else "DRAFT"; conn.execute("INSERT INTO consultations VALUES(?,?,?,?,?,?,?,?,?,?,?)",(cid,a["id"],a["patient_id"],d["id"],payload.transcript,payload.doctor_notes,"Structured draft: "+payload.doctor_notes,payload.final_note,state,now(),now() if state=="COMPLETED" else None))
        if state=="COMPLETED": conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",(uid("record"),a["patient_id"],"DOCTOR_VISIT","Endocrinology consultation",date.today().isoformat(),None,d["id"],"DOCTOR_NOTES",json.dumps({"final_note":payload.final_note}),payload.final_note,now())); conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",(a["id"],)); audit(conn,user.id,"DOCTOR_APPROVED_NOTE","consultation",cid)
        draft=ai_service.generate("consultation_draft",{"notes":payload.doctor_notes}); missing_ai=ai_service.generate("missing_information",{"missing":missing})
        return {"id":cid,"status":state,"ai_draft":draft.content,"missing_information":missing_ai.content["missing_items"],"ai":{"draft":draft.model_dump(),"missing":missing_ai.model_dump()}}
@app.get("/hospitals/{hospital_id}/capacity")
def hospital_capacity(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn: enforce_hospital(conn,user,hospital_id); return capacity(conn,hospital_id)
@app.get("/hospitals/{hospital_id}/departments")
def department_capacity(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn: enforce_hospital(conn,user,hospital_id); return rows(conn.execute("SELECT d.id,d.name,COUNT(b.id) total_beds,SUM(CASE WHEN b.status='OCCUPIED' THEN 1 ELSE 0 END) occupied,SUM(CASE WHEN b.status='AVAILABLE' THEN 1 ELSE 0 END) available FROM departments d LEFT JOIN beds b ON b.department_id=d.id WHERE d.hospital_id=? GROUP BY d.id,d.name",(hospital_id,)).fetchall())
@app.get("/hospitals/{hospital_id}/beds")
def bed_list(hospital_id:str,department_id:str|None=None,status_filter:str|None=None,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        enforce_hospital(conn,user,hospital_id)
        q="SELECT b.*,d.name department_name,p.id patient_id,u.name patient_name,a.admitted_at,a.expected_discharge_at FROM beds b JOIN departments d ON d.id=b.department_id LEFT JOIN admissions a ON a.bed_id=b.id AND a.status!='DISCHARGED' LEFT JOIN patients p ON p.id=a.patient_id LEFT JOIN users u ON u.id=p.user_id WHERE b.hospital_id=?"; args=(hospital_id,)
        if department_id: q+=" AND b.department_id=?"; args+=(department_id,)
        if status_filter: q+=" AND b.status=?"; args+=(status_filter,)
        return rows(conn.execute(q,args).fetchall())
@app.get("/hospitals/{hospital_id}/flow")
def patient_flow(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        enforce_hospital(conn,user,hospital_id)
        result=rows(conn.execute("SELECT status,COUNT(*) count FROM admissions WHERE hospital_id=? GROUP BY status",(hospital_id,)).fetchall()); blocked=conn.execute("SELECT COUNT(*) AS count FROM admissions a WHERE a.hospital_id=? AND EXISTS(SELECT 1 FROM discharge_blockers b WHERE b.admission_id=a.id AND b.status='OPEN')",(hospital_id,)).fetchone()["count"]
        return {"stages":result,"blocked":blocked}
@app.get("/discharge-blockers")
def blockers(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        hospital_id=hospital_scope(conn,user); return rows(conn.execute("SELECT b.*,a.patient_id,a.department_id,u.name patient_name,a.expected_discharge_at FROM discharge_blockers b JOIN admissions a ON a.id=b.admission_id JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=p.user_id WHERE a.hospital_id=? ORDER BY b.created_at",(hospital_id,)).fetchall())
@app.get("/hospitals/{hospital_id}/forecast")
def forecast(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        enforce_hospital(conn,user,hospital_id)
        cap=capacity(conn,hospital_id); usable=max(0,cap["expected_discharges"]-cap["delayed_discharges"]); future=cap["available"]+usable-cap["expected_incoming"]; return {"label":"capacity forecast","available_now":cap["available"],"expected_usable_discharges":usable,"expected_incoming":cap["expected_incoming"],"future_capacity":future,"predicted_shortage":max(0,-future),"method":"available + expected usable discharges - expected incoming"}
@app.get("/hospitals/{hospital_id}/recommendations")
def recommendations(hospital_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        enforce_hospital(conn,user,hospital_id); cap=capacity(conn,hospital_id); data=rows(conn.execute("SELECT t.*,b.blocker_type,a.patient_id FROM tasks t JOIN discharge_blockers b ON b.id=t.blocker_id JOIN admissions a ON a.id=t.admission_id WHERE a.hospital_id=? AND t.status!='COMPLETED' ORDER BY t.priority_score DESC",(hospital_id,)).fetchall())
        return [{"task_id":x["id"],"problem":x["blocker_type"],"patient":x["patient_id"],"action":x["title"],"impact":x["impact"],"priority":x["priority"],"why":f"Capacity has only {cap['available']} available beds; resolving this discharge blocker may free one bed."} for x in data]
@app.get("/tasks")
def list_tasks(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        hospital_id=hospital_scope(conn,user); data=rows(conn.execute("SELECT t.*,b.blocker_type,b.created_at blocker_created_at,a.patient_id FROM tasks t JOIN discharge_blockers b ON b.id=t.blocker_id JOIN admissions a ON a.id=t.admission_id WHERE a.hospital_id=? AND t.status!='COMPLETED' ORDER BY t.priority_score DESC",(hospital_id,)).fetchall()); cap=capacity(conn,hospital_id)
        for t in data: t["priority_score"]=priority_score({"created_at":t["blocker_created_at"],"estimated_minutes":one(conn,"SELECT estimated_minutes FROM discharge_blockers WHERE id=?",(t["blocker_id"],))["estimated_minutes"]},cap)
        return data
@app.patch("/tasks/{task_id}")
def update_task(task_id:str,payload:TaskUpdateIn,user:DemoUser=Depends(require("HOSPITAL_ADMIN","DOCTOR"))):
    with db() as conn:
        task=one(conn,"SELECT t.*,a.hospital_id FROM tasks t JOIN admissions a ON a.id=t.admission_id WHERE t.id=?",(task_id,))
        if not task: raise HTTPException(404,"Task not found")
        enforce_hospital(conn,user,task["hospital_id"])
        if user.role==Role.DOCTOR and task["assigned_role"]!="DOCTOR": raise HTTPException(403,"Task is not assigned to doctors")
        if task["status"]!="PENDING": raise HTTPException(409,f"Invalid task transition: {task['status']} to {payload.status}")
        conn.execute("UPDATE tasks SET status=?,assigned_role=COALESCE(?,assigned_role) WHERE id=?",(payload.status,payload.assigned_role,task_id)); audit(conn,user.id,"HOSPITAL_TASK_UPDATED","task",task_id,{"status":payload.status,"assigned_role":payload.assigned_role}); return {"id":task_id,"status":payload.status,"assigned_role":payload.assigned_role or task["assigned_role"]}
@app.post("/tasks/{task_id}/complete")
def complete_task(task_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN","DOCTOR"))):
    with db() as conn:
        t=one(conn,"SELECT t.*,a.hospital_id FROM tasks t JOIN admissions a ON a.id=t.admission_id WHERE t.id=?",(task_id,));
        if not t: raise HTTPException(404,"Task not found")
        enforce_hospital(conn,user,t["hospital_id"])
        if user.role==Role.DOCTOR and t["assigned_role"]!="DOCTOR": raise HTTPException(403,"Task is not assigned to doctors")
        if t["status"]!="IN_PROGRESS": raise HTTPException(409,"Task must be in progress before completion")
        conn.execute("UPDATE tasks SET status='COMPLETED',completed_at=? WHERE id=?",(now(),task_id)); conn.execute("UPDATE discharge_blockers SET status='RESOLVED',resolved_at=? WHERE id=?",(now(),t["blocker_id"])); unresolved=conn.execute("SELECT COUNT(*) AS count FROM discharge_blockers WHERE admission_id=? AND status='OPEN'",(t["admission_id"],)).fetchone()["count"]
        if unresolved==0: conn.execute("UPDATE admissions SET status='READY_FOR_DISCHARGE' WHERE id=?",(t["admission_id"],))
        notify(conn,role="HOSPITAL_ADMIN",hospital_id=t["hospital_id"],kind="SUCCESS",message=f"Task completed: {t['title']}",related_type="task",related_id=task_id); audit(conn,user.id,"BLOCKER_RESOLVED","blocker",t["blocker_id"]); audit(conn,user.id,"HOSPITAL_TASK_COMPLETED","task",task_id); return {"task_status":"COMPLETED","admission_status":"READY_FOR_DISCHARGE" if unresolved==0 else "BLOCKED"}
@app.post("/admissions/{admission_id}/discharge")
def discharge(admission_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        a=one(conn,"SELECT * FROM admissions WHERE id=?",(admission_id,)); blockers=conn.execute("SELECT COUNT(*) AS count FROM discharge_blockers WHERE admission_id=? AND status='OPEN'",(admission_id,)).fetchone()["count"]
        if not a: raise HTTPException(404,"Admission not found")
        enforce_hospital(conn,user,a["hospital_id"])
        if blockers or a["status"]!="READY_FOR_DISCHARGE" or not a["clinical_ready"]: raise HTTPException(409,"Admission is not ready for discharge")
        bed=one(conn,"SELECT status FROM beds WHERE id=? AND hospital_id=?",(a["bed_id"],a["hospital_id"]))
        if not bed or bed["status"]!="OCCUPIED": raise HTTPException(409,"Admission bed is not occupied")
        conn.execute("UPDATE admissions SET status='DISCHARGED' WHERE id=?",(admission_id,)); conn.execute("UPDATE beds SET status='CLEANING' WHERE id=?",(a["bed_id"],)); audit(conn,user.id,"PATIENT_DISCHARGED","admission",admission_id); return {"status":"DISCHARGED","bed_id":a["bed_id"],"bed_status":"CLEANING"}
@app.post("/beds/{bed_id}/complete-cleaning")
def complete_cleaning(bed_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        bed=one(conn,"SELECT hospital_id,status FROM beds WHERE id=?",(bed_id,))
        if not bed: raise HTTPException(404,"Bed not found")
        enforce_hospital(conn,user,bed["hospital_id"])
        if bed["status"]!="CLEANING": raise HTTPException(409,"Only cleaning beds can become available")
        conn.execute("UPDATE beds SET status='AVAILABLE' WHERE id=?",(bed_id,)); audit(conn,user.id,"BED_CLEANING_COMPLETED","bed",bed_id); return {"bed_id":bed_id,"status":"AVAILABLE"}
@app.get("/post-discharge/{patient_id}")
def checkin_history(patient_id:str,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        clinical_access(conn,patient_id,user)
        return rows(conn.execute("SELECT id,checkin_date,pain_score,temperature,medication_taken,symptoms,notes FROM checkins WHERE patient_id=? ORDER BY checkin_date DESC,created_at DESC",(patient_id,)).fetchall())
@app.post("/post-discharge/{patient_id}",status_code=201)
def checkin(patient_id:str,payload:CheckinIn,user:DemoUser=Depends(require("PATIENT"))):
    with db() as conn:
        clinical_access(conn,patient_id,user)
        conn.execute("INSERT INTO checkins (id,patient_id,discharge_id,checkin_date,pain_score,temperature,medication_taken,symptoms,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(uid("checkin"),patient_id,None,date.today().isoformat(),payload.pain_score,payload.temperature,int(payload.medication_taken),payload.symptoms,payload.notes,now())); history=rows(conn.execute("SELECT * FROM checkins WHERE patient_id=? ORDER BY checkin_date DESC,created_at DESC LIMIT 3",(patient_id,)).fetchall()); worsening=len(history)>=2 and (history[0]["pain_score"]>history[-1]["pain_score"] or history[0]["temperature"]>=38)
        if worsening:
            treating=one(conn,"SELECT d.user_id FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE a.patient_id=? AND a.status!='CANCELLED' ORDER BY a.created_at DESC LIMIT 1",(patient_id,))
            if treating: notify(conn,user_id=treating["user_id"],kind="WARNING",message="Patient post-discharge trend requires review.",related_type="patient",related_id=patient_id)
        return {"trend":"worsening" if worsening else "stable","requires_review":worsening}
@app.post("/cv-events",status_code=201)
def cv_event(payload:CVEventIn,user:DemoUser=Depends(cv_principal)):
    enforce_rate(f"cv:{user.id}",120,60)
    with db() as conn:
        if user.id=="cv_service":
            if payload.hospital_id!=os.getenv("CV_HOSPITAL_ID","hospital_caspian"): raise HTTPException(403,"CV service is not assigned to this hospital")
        else: enforce_hospital(conn,user,payload.hospital_id)
        event_time=payload.timestamp or datetime.now(timezone.utc)
        if event_time.tzinfo is None: event_time=event_time.replace(tzinfo=timezone.utc)
        if event_time>datetime.now(timezone.utc)+timedelta(minutes=5): raise HTTPException(422,"CV event timestamp cannot be in the future")
        occurred=event_time.isoformat(); recent=one(conn,"SELECT id FROM cv_events WHERE hospital_id=? AND room_id=? AND event_type=? AND occurred_at>? ORDER BY occurred_at DESC",(payload.hospital_id,payload.room_id,payload.event_type,(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()))
        if recent: return {"id":recent["id"],"status":"deduplicated","notification_created":False}
        eid=uid("cv"); conn.execute("INSERT INTO cv_events VALUES(?,?,?,?,?,?,?)",(eid,payload.hospital_id,payload.room_id,payload.event_type,payload.severity,payload.confidence,occurred)); conn.execute("INSERT INTO safety_event_details VALUES(?,?,?,?,?,?,?,?)",(eid,payload.patient_state,payload.previous_state,"ACTIVE",None,None,None,json.dumps(payload.metadata))); conn.execute("UPDATE rooms SET safety_status='HIGH_FALL_RISK' WHERE id=? AND hospital_id=?",(f"room_{payload.room_id}",payload.hospital_id)); notify(conn,role="HOSPITAL_ADMIN",hospital_id=payload.hospital_id,kind="CRITICAL",message=f"High fall risk — Room {payload.room_id}: patient attempting to stand without assistance.",related_type="cv_event",related_id=eid); audit(conn,user.id,"CV_EVENT_CREATED","cv_event",eid,{"hospital_id":payload.hospital_id,"room_id":payload.room_id,"state":payload.patient_state}); return {"id":eid,"status":"ACTIVE","notification_created":True}
@app.get("/notifications")
def notifications(unread_only:bool=False,kind:str|None=None,user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role==Role.HOSPITAL_ADMIN:
            sql="SELECT * FROM notifications WHERE (user_id=? OR (role=? AND hospital_id=?))"; args=(user.id,user.role,hospital_scope(conn,user))
        else: sql="SELECT * FROM notifications WHERE user_id=?"; args=(user.id,)
        if unread_only: sql+=" AND read_at IS NULL"
        if kind: sql+=" AND type=?"; args+=(kind,)
        return rows(conn.execute(sql+" ORDER BY created_at DESC",args).fetchall())
@app.get("/notifications/unread-count")
def unread_count(user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role==Role.HOSPITAL_ADMIN: count=conn.execute("SELECT COUNT(*) AS count FROM notifications WHERE (user_id=? OR (role=? AND hospital_id=?)) AND read_at IS NULL",(user.id,user.role,hospital_scope(conn,user))).fetchone()["count"]
        else: count=conn.execute("SELECT COUNT(*) AS count FROM notifications WHERE user_id=? AND read_at IS NULL",(user.id,)).fetchone()["count"]
        return {"count":count}
@app.post("/notifications/read")
def mark_read(payload:ReadIn,user:DemoUser=Depends(current_user)):
    with db() as conn:
        hospital_id=hospital_scope(conn,user) if user.role==Role.HOSPITAL_ADMIN else None
        if payload.ids:
            for item in payload.ids: conn.execute("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR (role=? AND hospital_id=?))",(now(),item,user.id,user.role,hospital_id))
        elif user.role==Role.HOSPITAL_ADMIN: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=? OR (role=? AND hospital_id=?)",(now(),user.id,user.role,hospital_id))
        else: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=?",(now(),user.id))
        return {"status":"ok"}
@app.patch("/notifications/read-all")
def mark_all_read(user:DemoUser=Depends(current_user)):
    with db() as conn:
        if user.role==Role.HOSPITAL_ADMIN: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=? OR (role=? AND hospital_id=?)",(now(),user.id,user.role,hospital_scope(conn,user)))
        else: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=?",(now(),user.id))
        return {"status":"ok"}
@app.patch("/notifications/{notification_id}/read")
def mark_one_read(notification_id:str,user:DemoUser=Depends(current_user)):
    with db() as conn:
        hospital_id=hospital_scope(conn,user) if user.role==Role.HOSPITAL_ADMIN else None
        updated=conn.execute("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR (role=? AND hospital_id=?))",(now(),notification_id,user.id,user.role,hospital_id))
        if updated.rowcount!=1: raise HTTPException(404,"Notification not found")
        return {"id":notification_id,"status":"read"}
@app.get("/safety/events")
def safety_events(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        hospital_id=hospital_scope(conn,user)
        events=rows(conn.execute("SELECT e.*,d.patient_state,d.previous_state,d.status,d.acknowledged_at,d.resolved_at FROM cv_events e LEFT JOIN safety_event_details d ON d.event_id=e.id WHERE e.hospital_id=? ORDER BY e.occurred_at DESC",(hospital_id,)).fetchall())
        grouped:dict[str,list[dict[str,Any]]]=defaultdict(list)
        for task in rows(conn.execute("SELECT id,event_id,room_id,title,assigned_role,priority,status,created_at,completed_at FROM safety_tasks WHERE event_id IN (SELECT id FROM cv_events WHERE hospital_id=?) ORDER BY created_at DESC",(hospital_id,)).fetchall()): grouped[task["event_id"]].append(task)
        for event in events: event["nurse_tasks"]=grouped.get(event["id"],[])
        return events
@app.patch("/cv-events/{event_id}/acknowledge")
def acknowledge_event(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        event=one(conn,"SELECT e.hospital_id,d.status FROM cv_events e JOIN safety_event_details d ON d.event_id=e.id WHERE e.id=?",(event_id,))
        if not event: raise HTTPException(404,"Safety event not found")
        enforce_hospital(conn,user,event["hospital_id"])
        if event["status"]!="ACTIVE": raise HTTPException(409,"Only active events can be acknowledged")
        conn.execute("UPDATE safety_event_details SET status='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=? WHERE event_id=?",(now(),user.id,event_id)); audit(conn,user.id,"CV_EVENT_ACKNOWLEDGED","cv_event",event_id); return {"id":event_id,"status":"ACKNOWLEDGED"}
@app.post("/cv-events/{event_id}/send-nurse")
def send_nurse(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        event=one(conn,"SELECT e.*,d.status event_status FROM cv_events e JOIN safety_event_details d ON d.event_id=e.id WHERE e.id=?",(event_id,));
        if not event: raise HTTPException(404,"Safety event not found")
        enforce_hospital(conn,user,event["hospital_id"])
        if event["event_status"] not in {"ACTIVE","ACKNOWLEDGED"}: raise HTTPException(409,"Resolved events cannot create nurse tasks")
        existing=one(conn,"SELECT id,status FROM safety_tasks WHERE event_id=? AND status!='COMPLETED'",(event_id,))
        if existing: return {"id":existing["id"],"status":existing["status"],"deduplicated":True}
        task_id=uid("safety_task"); conn.execute("INSERT INTO safety_tasks VALUES(?,?,?,?,?,?,?,?,?)",(task_id,event_id,event["room_id"],f"Assist Patient — Room {event['room_id']}","NURSE","CRITICAL","PENDING",now(),None)); notify(conn,role="HOSPITAL_ADMIN",hospital_id=event["hospital_id"],kind="TASK",message=f"Nurse assistance task created for Room {event['room_id']}.",related_type="safety_task",related_id=task_id); audit(conn,user.id,"NURSE_TASK_CREATED","safety_task",task_id); return {"id":task_id,"status":"PENDING"}
@app.patch("/cv-events/{event_id}/resolve")
def resolve_event(event_id:str,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        event=one(conn,"SELECT e.hospital_id,e.room_id,d.status FROM cv_events e JOIN safety_event_details d ON d.event_id=e.id WHERE e.id=?",(event_id,))
        if not event: raise HTTPException(404,"Safety event not found")
        enforce_hospital(conn,user,event["hospital_id"])
        if event["status"]!="ACKNOWLEDGED": raise HTTPException(409,"Event must be acknowledged before resolution")
        conn.execute("UPDATE safety_event_details SET status='RESOLVED',resolved_at=? WHERE event_id=?",(now(),event_id)); conn.execute("UPDATE rooms SET safety_status='STABLE' WHERE id=? AND hospital_id=?",(f"room_{event['room_id']}",event["hospital_id"])); audit(conn,user.id,"CV_EVENT_RESOLVED","cv_event",event_id); return {"id":event_id,"status":"RESOLVED"}
@app.get("/demo/assets/lab-report")
def demo_lab_report(user:DemoUser=Depends(require("PATIENT"))):
    if not demo_enabled(): raise HTTPException(404,"Not found")
    path=ROOT/"demo_documents"/"hasan_lab_report.pdf"
    if not path.exists(): raise HTTPException(404,"Demo document is unavailable")
    return FileResponse(path,media_type="application/pdf",filename="hasan-demo-lab-report.pdf")
@app.post("/demo/reset")
def reset_demo(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    if not demo_enabled(): raise HTTPException(404,"Not found")
    with db() as conn:
        paths=reset_demo_data(conn); readiness=demo_readiness(conn,ROOT/"demo_documents"/"hasan_lab_report.pdf")
    _remove_demo_uploads(paths); RATE_BUCKETS.clear()
    return {"status":"reset","message":"Demo data restored.","ready":readiness["ready"],"version":readiness["version"]}
@app.get("/audit")
def audits(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:
        hospital_id=hospital_scope(conn,user)
        query="""SELECT a.* FROM audit_events a WHERE
        (a.entity_type='task' AND EXISTS(SELECT 1 FROM tasks t JOIN admissions x ON x.id=t.admission_id WHERE t.id=a.entity_id AND x.hospital_id=?)) OR
        (a.entity_type='blocker' AND EXISTS(SELECT 1 FROM discharge_blockers b JOIN admissions x ON x.id=b.admission_id WHERE b.id=a.entity_id AND x.hospital_id=?)) OR
        (a.entity_type='admission' AND EXISTS(SELECT 1 FROM admissions x WHERE x.id=a.entity_id AND x.hospital_id=?)) OR
        (a.entity_type='bed' AND EXISTS(SELECT 1 FROM beds b WHERE b.id=a.entity_id AND b.hospital_id=?)) OR
        (a.entity_type='cv_event' AND EXISTS(SELECT 1 FROM cv_events e WHERE e.id=a.entity_id AND e.hospital_id=?)) OR
        (a.entity_type='safety_task' AND EXISTS(SELECT 1 FROM safety_tasks s JOIN cv_events e ON e.id=s.event_id WHERE s.id=a.entity_id AND e.hospital_id=?))
        ORDER BY a.created_at DESC"""
        return rows(conn.execute(query,(hospital_id,)*6).fetchall())
@app.get("/ai/lab-explanation/{patient_id}")
def ai_explain(patient_id:str,user:DemoUser=Depends(current_user)):
    enforce_rate(f"ai:{user.id}",30,60)
    with db() as conn:
        clinical_access(conn,patient_id,user,("LAB_RESULTS",))
        data=trends(conn,patient_id); target=next((x for x in data if x["metric"]=="HbA1c"),data[0] if data else None)
        if not target: raise HTTPException(404,"No trends available")
        result=ai_service.generate("lab_explanation",{"trend":target}); return {"data":target,"ai":result.model_dump()}
@app.post("/ai/specialty-recommendation")
def ai_specialty(payload:AITextIn,user:DemoUser=Depends(current_user)):
    enforce_rate(f"ai:{user.id}",30,60)
    with db() as conn:
        patient_id=payload.patient_id or "patient_hasan"; clinical_access(conn,patient_id,user,("LAB_RESULTS",)); data=trends(conn,patient_id); deterministic=specialty_for(data); result=ai_service.generate("specialty",{"specialty":deterministic["suggested_specialty"],"reason":deterministic["reason"]}); return {"deterministic":deterministic,"ai":result.model_dump()}
@app.post("/ai/record-conflict-explanation")
def ai_conflict(payload:AITextIn,user:DemoUser=Depends(current_user)):
    enforce_rate(f"ai:{user.id}",30,60)
    with db() as conn:
        patient_id=payload.patient_id or "patient_hasan"; allowed=clinical_access(conn,patient_id,user,("LAB_RESULTS","DIAGNOSES")); found=conflicts(conn,patient_id,None if user.role==Role.PATIENT else allowed); return {"conflicts":found,"ai":ai_service.generate("record_conflict",{"conflicts":found}).model_dump()}
@app.post("/ai/post-discharge-summary")
def ai_post_discharge(payload:AITextIn,user:DemoUser=Depends(current_user)):
    enforce_rate(f"ai:{user.id}",30,60)
    return {"ai":ai_service.generate("post_discharge",{}).model_dump()}
@app.post("/ai/hospital-recommendation")
def ai_hospital(payload:AITextIn,user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    enforce_rate(f"ai:{user.id}",30,60)
    with db() as conn:
        task=one(conn,"SELECT t.*,a.hospital_id FROM tasks t JOIN admissions a ON a.id=t.admission_id WHERE t.id=?",(payload.task_id or "task_104",));
        if not task: raise HTTPException(404,"Task not found")
        enforce_hospital(conn,user,task["hospital_id"])
        return {"ai":ai_service.generate("hospital_recommendation",{"title":task["title"],"reason":"The patient is discharge-ready and capacity is constrained.","impact":task["impact"]}).model_dump()}
