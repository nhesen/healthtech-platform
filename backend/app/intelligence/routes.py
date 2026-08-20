"""REST surface for healthcare intelligence. Registered after core FastAPI app helpers exist."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .engines import (
    BREAK_GLASS_MINUTES,
    active_break_glass,
    active_prescriptions,
    emergency_summary,
    enrich_alert,
    epidemic_from_reports,
    evaluate_medications,
    hospital_snapshot,
    match_blood,
    open_break_glass,
    persist_alerts,
    recommend_hospital,
)
from ..ai import ai_service

router = APIRouter(tags=["intelligence"])


class AlertStatusIn(BaseModel):
    status: Literal["REVIEWED", "RESOLVED", "DISMISSED"]


class BreakGlassIn(BaseModel):
    patient_id: str = Field(min_length=3, max_length=80)
    reason: Literal["Patient unconscious", "Emergency treatment required", "Critical medical situation"]
    device: str | None = Field(None, max_length=120)


class RoutingIn(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "CRITICAL"
    required_specialty: str | None = Field("ICU", max_length=80)
    needs_icu: bool = True
    equipment: str | None = Field(None, max_length=80)
    origin_lat: float = Field(40.4093, ge=-90, le=90)
    origin_lng: float = Field(49.8671, ge=-180, le=180)


class ResourceRequestIn(BaseModel):
    hospital_id: str = "hospital_caspian"
    resource_type: Literal["BLOOD", "ICU", "VENTILATOR"] = "BLOOD"
    blood_type: str = Field("O-", min_length=1, max_length=8)
    units_needed: int = Field(4, ge=1, le=50)
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "CRITICAL"


def _helpers():
    from ..main import DemoUser, Role, audit, clinical_access, current_user, db, enforce_rate, hospital_scope, now, notify, one, require, rows, uid
    return {
        "DemoUser": DemoUser, "Role": Role, "audit": audit, "clinical_access": clinical_access,
        "current_user": current_user, "db": db, "enforce_rate": enforce_rate, "hospital_scope": hospital_scope,
        "now": now, "notify": notify, "one": one, "require": require, "rows": rows, "uid": uid,
    }


H = _helpers


def _can_view_patient_clinical(conn, patient_id: str, user) -> bool:
    from ..main import Role, clinical_access
    if user.role == Role.PATIENT:
        clinical_access(conn, patient_id, user)
        return True
    if user.role == Role.DOCTOR:
        try:
            clinical_access(conn, patient_id, user, ("MEDICATIONS",))
            return True
        except HTTPException:
            if active_break_glass(conn, user.id, patient_id):
                return True
            raise
    if active_break_glass(conn, user.id, patient_id):
        return True
    raise HTTPException(403, "Emergency break-glass access is required for this snapshot")


def register(app) -> None:
    """Attach routes once main.py has defined auth helpers."""
    from ..main import DemoUser, Role, audit, clinical_access, current_user, db, enforce_rate, hospital_scope, now, notify, one, require, rows, uid

    def patient_visible(conn, patient_id: str, user: DemoUser) -> None:
        if user.role == Role.PATIENT:
            clinical_access(conn, patient_id, user)
            return
        if user.role == Role.DOCTOR:
            prescribed = conn.execute(
                "SELECT 1 FROM prescriptions p JOIN doctors d ON d.id=p.doctor_id WHERE d.user_id=? AND p.patient_id=? AND p.status='ACTIVE'",
                (user.id, patient_id),
            ).fetchone()
            if prescribed:
                return
            try:
                clinical_access(conn, patient_id, user, ("MEDICATIONS",))
                return
            except HTTPException:
                if active_break_glass(conn, user.id, patient_id):
                    return
                raise
        if user.role == Role.HOSPITAL_ADMIN and active_break_glass(conn, user.id, patient_id):
            return
        raise HTTPException(403, "Hospital administrators cannot access full clinical records")

    @app.get("/intelligence/overview")
    def intelligence_overview(user: DemoUser = Depends(require("HOSPITAL_ADMIN", "DOCTOR"))):
        with db() as conn:
            critical = conn.execute("SELECT COUNT(*) AS c FROM medication_alerts WHERE status='NEW' AND severity IN ('HIGH','CRITICAL')").fetchone()["c"]
            glass_today = conn.execute("SELECT COUNT(*) AS c FROM emergency_access WHERE started_at>=?", (now()[:10],)).fetchone()["c"]
            snap = hospital_snapshot(conn)
            caspian = next((x for x in snap if x["id"] == "hospital_caspian"), snap[0] if snap else None)
            blood_open = conn.execute("SELECT COUNT(*) AS c FROM resource_requests WHERE status='OPEN'").fetchone()["c"]
            signals = epidemic_from_reports(conn)
            routing_busy = sum(1 for x in snap if x["er_load_percent"] >= 75)
            return {
                "title": "HealthTech Intelligence",
                "critical_medication_alerts": critical,
                "hospital_capacity_percent": caspian["er_load_percent"] if caspian else None,
                "hospital_load": caspian["load"] if caspian else None,
                "emergency_routing_cases": routing_busy,
                "blood_resource_alerts": blood_open,
                "epidemiology_signals": len(signals),
                "break_glass_today": glass_today,
                "disclaimer": "Decision support for professional review. Not an autonomous clinical system.",
            }

    @app.get("/medications")
    def list_medications(user: DemoUser = Depends(current_user)):
        with db() as conn:
            return rows(conn.execute("SELECT id,name,active_ingredient,drug_class FROM medications ORDER BY name").fetchall())

    @app.get("/prescriptions")
    def list_prescriptions(patient_id: str = "patient_hasan", user: DemoUser = Depends(current_user)):
        with db() as conn:
            patient_visible(conn, patient_id, user)
            return active_prescriptions(conn, patient_id)

    @app.post("/medication-safety/scan")
    def scan_medications(patient_id: str = "patient_hasan", user: DemoUser = Depends(require("DOCTOR", "HOSPITAL_ADMIN"))):
        enforce_rate(f"medscan:{user.id}", 20, 60)
        with db() as conn:
            if user.role == Role.DOCTOR:
                prescribed = one(conn, "SELECT 1 AS ok FROM prescriptions p JOIN doctors d ON d.id=p.doctor_id WHERE d.user_id=? AND p.patient_id=? AND p.status='ACTIVE'", (user.id, patient_id))
                if not prescribed:
                    try:
                        clinical_access(conn, patient_id, user, ("MEDICATIONS",))
                    except HTTPException:
                        if not active_break_glass(conn, user.id, patient_id):
                            raise
            findings = persist_alerts(conn, patient_id, user.id, notify, uid, now)
            audit(conn, user.id, "MEDICATION_SAFETY_SCAN", "patient", patient_id, {"count": len(findings)})
            return [enrich_alert(conn, item) for item in findings]

    @app.get("/medication-alerts")
    def list_alerts(patient_id: str | None = None, user: DemoUser = Depends(current_user)):
        with db() as conn:
            if user.role == Role.PATIENT:
                own = one(conn, "SELECT id FROM patients WHERE user_id=?", (user.id,))
                if not own: raise HTTPException(404, "Patient not found")
                patient_id = own["id"]
            if patient_id:
                patient_visible(conn, patient_id, user)
                data = rows(conn.execute("SELECT * FROM medication_alerts WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall())
            elif user.role == Role.HOSPITAL_ADMIN:
                data = rows(conn.execute("SELECT * FROM medication_alerts ORDER BY created_at DESC").fetchall())
            elif user.role == Role.DOCTOR:
                data = rows(conn.execute(
                    """SELECT a.* FROM medication_alerts a
                       WHERE a.patient_id IN (
                         SELECT patient_id FROM prescriptions
                         WHERE doctor_id IN (SELECT id FROM doctors WHERE user_id=?) AND status='ACTIVE'
                       )
                       ORDER BY a.created_at DESC""",
                    (user.id,),
                ).fetchall())
            else:
                data = []
            return [enrich_alert(conn, item) for item in data]

    @app.patch("/medication-alerts/{alert_id}")
    def update_alert(alert_id: str, payload: AlertStatusIn, user: DemoUser = Depends(require("DOCTOR", "HOSPITAL_ADMIN"))):
        with db() as conn:
            alert = one(conn, "SELECT * FROM medication_alerts WHERE id=?", (alert_id,))
            if not alert: raise HTTPException(404, "Alert not found")
            conn.execute("UPDATE medication_alerts SET status=?,updated_at=? WHERE id=?", (payload.status, now(), alert_id))
            audit(conn, user.id, "MEDICATION_ALERT_"+payload.status, "medication_alert", alert_id, {"status": payload.status})
            return {**alert, "status": payload.status}

    @app.get("/emergency/summary/{patient_id}")
    def get_emergency_summary(patient_id: str, user: DemoUser = Depends(current_user)):
        with db() as conn:
            patient_visible(conn, patient_id, user)
            alerts = evaluate_medications(conn, patient_id)
            glass = active_break_glass(conn, user.id, patient_id)
            summary = emergency_summary(conn, patient_id, alerts)
            if not summary: raise HTTPException(404, "Patient not found")
            summary["access"] = "BREAK_GLASS" if glass else "AUTHORIZED"
            summary["break_glass"] = glass
            return summary

    @app.post("/emergency/break-glass")
    def break_glass(payload: BreakGlassIn, request: Request, user: DemoUser = Depends(require("DOCTOR", "HOSPITAL_ADMIN"))):
        enforce_rate(f"glass:{user.id}", 8, 60)
        with db() as conn:
            patient = one(conn, "SELECT id FROM patients WHERE id=?", (payload.patient_id,))
            if not patient: raise HTTPException(404, "Patient not found")
            existing = active_break_glass(conn, user.id, payload.patient_id)
            if existing:
                return {**existing, "deduplicated": True, "duration_minutes": BREAK_GLASS_MINUTES}
            access = open_break_glass(conn, user.id, payload.patient_id, payload.reason, payload.device or request.headers.get("user-agent", "")[:120], uid)
            audit(conn, user.id, "BREAK_GLASS", "patient", payload.patient_id, {
                "reason": payload.reason, "access_type": "BREAK_GLASS", "duration_minutes": BREAK_GLASS_MINUTES,
                "device": access["device"], "expires_at": access["expires_at"],
            })
            notify(conn, role="HOSPITAL_ADMIN", hospital_id="hospital_caspian", kind="WARNING",
                   message=f"Break-glass access opened for {payload.patient_id} by {user.name}. Reason: {payload.reason}",
                   related_type="emergency_access", related_id=access["id"])
            return {**access, "duration_minutes": BREAK_GLASS_MINUTES}

    @app.get("/emergency/access")
    def list_break_glass(user: DemoUser = Depends(current_user)):
        with db() as conn:
            if user.role == Role.HOSPITAL_ADMIN:
                data = rows(conn.execute("SELECT * FROM emergency_access ORDER BY started_at DESC").fetchall())
            else:
                data = rows(conn.execute("SELECT * FROM emergency_access WHERE actor_id=? ORDER BY started_at DESC", (user.id,)).fetchall())
            return data

    @app.get("/hospitals/network")
    def network(user: DemoUser = Depends(require("HOSPITAL_ADMIN", "DOCTOR"))):
        with db() as conn:
            return hospital_snapshot(conn)

    @app.post("/hospitals/recommend")
    def recommend(payload: RoutingIn, user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            result = recommend_hospital(
                conn, origin_lat=payload.origin_lat, origin_lng=payload.origin_lng, severity=payload.severity,
                required_specialty=payload.required_specialty, needs_icu=payload.needs_icu, equipment=payload.equipment,
            )
            chosen = result.get("recommended") or {}
            explanation = ai_service.generate("routing_explanation", {
                "hospital": chosen.get("name"), "reasons": result.get("reasons"), "severity": payload.severity,
            })
            result["ai"] = explanation.model_dump()
            audit(conn, user.id, "HOSPITAL_ROUTE", "hospital", chosen.get("id") or "none", {"severity": payload.severity})
            return result

    @app.get("/blood-bank")
    def blood_bank(user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            return rows(conn.execute(
                "SELECT b.*,h.name hospital_name FROM blood_inventory b JOIN hospitals h ON h.id=b.hospital_id ORDER BY b.blood_type,h.name"
            ).fetchall())

    @app.get("/resources/match")
    def resources_match(blood_type: str = "O-", units: int = 4, hospital_id: str = "hospital_caspian", user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            hospital_scope(conn, user)
            return match_blood(conn, requesting_hospital_id=hospital_id, blood_type=blood_type, units_needed=units)

    @app.post("/resource-matching")
    def create_match(payload: ResourceRequestIn, user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            hospital_scope(conn, user)
            request_id = uid("rreq")
            conn.execute(
                "INSERT INTO resource_requests VALUES(?,?,?,?,?,?,?,?)",
                (request_id, payload.hospital_id, payload.resource_type, payload.blood_type, payload.units_needed, payload.priority, "OPEN", now()),
            )
            matches = match_blood(conn, requesting_hospital_id=payload.hospital_id, blood_type=payload.blood_type, units_needed=payload.units_needed)
            stored = []
            for item in matches[:3]:
                match_id = uid("rmatch")
                conn.execute(
                    "INSERT INTO resource_matches VALUES(?,?,?,?,?,?,?,?)",
                    (match_id, request_id, item["hospital_id"], item["units"], item["distance_km"], item["travel_minutes"], item["priority"], now()),
                )
                stored.append({**item, "id": match_id})
            if stored:
                conn.execute("UPDATE resource_requests SET status='MATCHED' WHERE id=?", (request_id,))
            audit(conn, user.id, "RESOURCE_MATCH", "resource_request", request_id, {"blood_type": payload.blood_type, "matches": len(stored)})
            return {"request_id": request_id, "matches": stored, "best": stored[0] if stored else None}

    @app.get("/epidemics/signals")
    def epidemic_signals(user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            signals = epidemic_from_reports(conn)
            for item in signals:
                explanation = ai_service.generate("epidemic_explanation", item)
                item["ai"] = explanation.model_dump()
                existing = one(conn, "SELECT id FROM epidemic_signals WHERE region=? AND signal=?", (item["region"], item["signal"]))
                if not existing:
                    conn.execute(
                        "INSERT INTO epidemic_signals VALUES(?,?,?,?,?,?,?,?)",
                        (uid("epi"), item["region"], item["signal"], item["change_percent"], item["confidence"], item["risk"], item["recommendation"], now()),
                    )
            return signals

    @app.get("/epidemics/regions")
    def epidemic_regions(user: DemoUser = Depends(require("HOSPITAL_ADMIN"))):
        with db() as conn:
            return rows(conn.execute(
                "SELECT region,symptom,SUM(count) total,MAX(report_date) latest FROM symptom_reports GROUP BY region,symptom ORDER BY region,symptom"
            ).fetchall())

    @app.get("/medication-safety/explain/{alert_id}")
    def explain_alert(alert_id: str, user: DemoUser = Depends(current_user)):
        enforce_rate(f"ai:{user.id}", 30, 60)
        with db() as conn:
            alert = one(conn, "SELECT * FROM medication_alerts WHERE id=?", (alert_id,))
            if not alert: raise HTTPException(404, "Alert not found")
            patient_visible(conn, alert["patient_id"], user)
            packed = enrich_alert(conn, alert)
            result = ai_service.generate("medication_explanation", packed)
            return {"alert": packed, "ai": result.model_dump()}
