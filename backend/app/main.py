from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
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
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, actor_id TEXT, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL);
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
class ConsentIn(BaseModel): doctor_id:str; categories:list[str]; hours:int=Field(24,ge=1,le=168)
class ConsultationIn(BaseModel): appointment_id:str; transcript:str=""; doctor_notes:str=""; final_note:str|None=None; complete:bool=False
class CheckinIn(BaseModel): pain_score:int=Field(ge=1,le=10); temperature:float; medication_taken:bool; symptoms:str=""; notes:str=""
class CVEventIn(BaseModel): room_id:str; event_type:Literal["FALL_RISK"]; severity:Literal["HIGH","CRITICAL","WARNING"]="HIGH"; confidence:float=Field(ge=0,le=1); timestamp:datetime|None=None
class ReadIn(BaseModel): ids:list[str]=[]

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
        cost=insurance(p["insurance_plan"],d["specialty"],d["price"]); aid=uid("appt"); conn.execute("INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?)",(aid,p["id"],payload.doctor_id,payload.slot_id,"SCHEDULED",payload.reason,json.dumps(cost),now())); conn.execute("UPDATE availability SET status='BOOKED' WHERE id=?",(payload.slot_id,)); notify(conn,user_id=user.id,kind="SUCCESS",message="Appointment confirmed.",related_type="appointment",related_id=aid); audit(conn,user.id,"APPOINTMENT_BOOKED","appointment",aid,cost)
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
        return {"patient":{"id":patient_id,"name":p["name"],"dob":p["dob"]},"reason_for_visit":"Endocrinology consultation","allowed_categories":allowed,"relevant_metrics":relevant,"medications":json.loads(p["medications_json"]) if "MEDICATIONS" in allowed else [],"allergies":json.loads(p["allergies_json"]),"important_history":[r["title"] for r in records],"warnings":conflicts(conn,patient_id),"summary":"HbA1c has increased from 5.4 to 6.3 over time. This is not a diagnosis; clinician review is required.","provider":"MockAIProvider"}
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
        return {"id":cid,"status":state,"ai_draft":"Structured draft: "+payload.doctor_notes,"missing_information":missing}
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
        eid=uid("cv"); conn.execute("INSERT INTO cv_events VALUES(?,?,?,?,?,?)",(eid,payload.room_id,payload.event_type,payload.severity,payload.confidence,(payload.timestamp or datetime.now(timezone.utc)).isoformat())); notify(conn,role="HOSPITAL_ADMIN",kind="CRITICAL",message=f"Room {payload.room_id}: patient attempting to stand without assistance.",related_type="cv_event",related_id=eid); return {"id":eid,"status":"alert_created"}
@app.get("/notifications")
def notifications(user:DemoUser=Depends(current_user)):
    with db() as conn:return rows(conn.execute("SELECT * FROM notifications WHERE user_id=? OR role=? ORDER BY created_at DESC",(user.id,user.role)).fetchall())
@app.post("/notifications/read")
def mark_read(payload:ReadIn,user:DemoUser=Depends(current_user)):
    with db() as conn:
        if payload.ids: conn.executemany("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR role=?)",[(now(),item,user.id,user.role) for item in payload.ids])
        else: conn.execute("UPDATE notifications SET read_at=? WHERE user_id=? OR role=?",(now(),user.id,user.role))
        return {"status":"ok"}
@app.get("/safety/events")
def safety_events(user:DemoUser=Depends(require("HOSPITAL_ADMIN"))):
    with db() as conn:return rows(conn.execute("SELECT * FROM cv_events ORDER BY occurred_at DESC",).fetchall())
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
        data=trends(conn,patient_id); return {"provider":"MockAIProvider","summary":"HbA1c has increased consistently over recent measurements. An endocrinology consultation may be useful. This is not a diagnosis.","data":data}
