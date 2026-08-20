"""Deterministic healthcare intelligence engines. AI only explains the result."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
BREAK_GLASS_MINUTES = 5


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utcnow()).isoformat()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def travel_minutes(km: float) -> int:
    return max(4, round(km / 0.65))


def load_band(percent: int) -> str:
    if percent >= 90: return "CRITICAL"
    if percent >= 75: return "HIGH LOAD"
    if percent >= 50: return "MEDIUM LOAD"
    return "LOW LOAD"


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def active_prescriptions(conn, patient_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        """SELECT p.id,p.patient_id,p.doctor_id,p.medication_id,p.dosage,p.dose_mg,p.status,p.started_at,
                  m.name medication_name,m.active_ingredient,m.drug_class,m.penicillin_class,m.high_dose_mg,
                  u.name doctor_name,d.specialty
           FROM prescriptions p
           JOIN medications m ON m.id=p.medication_id
           JOIN doctors d ON d.id=p.doctor_id
           JOIN users u ON u.id=d.user_id
           WHERE p.patient_id=? AND p.status='ACTIVE' ORDER BY p.started_at""",
        (patient_id,),
    ).fetchall()]


def patient_allergies(conn, patient_id: str) -> list[str]:
    row = conn.execute("SELECT allergies_json FROM patients WHERE id=?", (patient_id,)).fetchone()
    if not row: return []
    raw = json.loads(row["allergies_json"] or "[]")
    names = []
    for item in raw:
        name = item.get("name") if isinstance(item, dict) else str(item)
        if name: names.append(name.lower())
    return names


def interaction_catalog(conn) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute("SELECT * FROM medication_interactions").fetchall()]


def evaluate_medications(conn, patient_id: str) -> list[dict[str, Any]]:
    """Rule engine only. Does not persist and does not call an LLM."""
    rx = active_prescriptions(conn, patient_id)
    allergies = patient_allergies(conn, patient_id)
    catalog = interaction_catalog(conn)
    catalog_map = {pair_key(item["medication_a"], item["medication_b"]): item for item in catalog}
    findings: list[dict[str, Any]] = []

    for item in rx:
        if item["penicillin_class"] and any("penicillin" in allergy for allergy in allergies):
            findings.append({
                "alert_type": "ALLERGY",
                "severity": "CRITICAL",
                "medication_a": item["medication_name"],
                "medication_b": None,
                "doctor_a": item["doctor_id"],
                "doctor_b": None,
                "explanation": f"{item['medication_name']} belongs to the penicillin class and conflicts with a recorded penicillin allergy.",
                "recommended_action": "Do not administer. Substitute a non-penicillin agent after clinician review.",
            })
        if item["high_dose_mg"] and item["dose_mg"] and item["dose_mg"] >= item["high_dose_mg"]:
            findings.append({
                "alert_type": "DOSE",
                "severity": "MEDIUM",
                "medication_a": item["medication_name"],
                "medication_b": None,
                "doctor_a": item["doctor_id"],
                "doctor_b": None,
                "explanation": f"{item['medication_name']} dose {item['dosage']} meets or exceeds the demo high-dose threshold of {item['high_dose_mg']} mg.",
                "recommended_action": "Confirm indication and renal function before continuation.",
            })

    for i, left in enumerate(rx):
        for right in rx[i + 1:]:
            key = pair_key(left["medication_id"], right["medication_id"])
            rule = catalog_map.get(key)
            if rule:
                findings.append({
                    "alert_type": rule["interaction_type"],
                    "severity": rule["severity"],
                    "medication_a": left["medication_name"],
                    "medication_b": right["medication_name"],
                    "doctor_a": left["doctor_id"],
                    "doctor_b": right["doctor_id"],
                    "explanation": rule["explanation"],
                    "recommended_action": rule["recommended_action"],
                })
            if left["active_ingredient"] == right["active_ingredient"]:
                findings.append({
                    "alert_type": "SAME_INGREDIENT",
                    "severity": "HIGH",
                    "medication_a": left["medication_name"],
                    "medication_b": right["medication_name"],
                    "doctor_a": left["doctor_id"],
                    "doctor_b": right["doctor_id"],
                    "explanation": f"{left['medication_name']} and {right['medication_name']} share the active ingredient {left['active_ingredient']}.",
                    "recommended_action": "Stop the duplicate product after clinician review to avoid stacked exposure.",
                })
            elif left["medication_name"].split()[0].lower() == right["medication_name"].split()[0].lower():
                findings.append({
                    "alert_type": "DUPLICATE",
                    "severity": "MEDIUM",
                    "medication_a": left["medication_name"],
                    "medication_b": right["medication_name"],
                    "doctor_a": left["doctor_id"],
                    "doctor_b": right["doctor_id"],
                    "explanation": f"Two prescriptions use the same medication name {left['medication_name']}.",
                    "recommended_action": "Reconcile the medication list with both prescribers.",
                })
            if left["doctor_id"] != right["doctor_id"] and (
                left["drug_class"] == right["drug_class"] or left["active_ingredient"] == right["active_ingredient"] or rule
            ):
                findings.append({
                    "alert_type": "MULTI_PRESCRIBER",
                    "severity": "MEDIUM" if not rule else rule["severity"],
                    "medication_a": left["medication_name"],
                    "medication_b": right["medication_name"],
                    "doctor_a": left["doctor_id"],
                    "doctor_b": right["doctor_id"],
                    "explanation": f"{left['specialty']} and {right['specialty']} independently prescribed overlapping medications.",
                    "recommended_action": "Coordinate both prescribers before the combination is continued.",
                })

    deduped: dict[tuple, dict[str, Any]] = {}
    for item in findings:
        key = (item["alert_type"], item["medication_a"], item["medication_b"], item["doctor_a"], item["doctor_b"])
        previous = deduped.get(key)
        if not previous or SEVERITY_RANK[item["severity"]] > SEVERITY_RANK[previous["severity"]]:
            deduped[key] = item
    ranked = sorted(deduped.values(), key=lambda x: (-SEVERITY_RANK[x["severity"]], x["alert_type"]))
    return ranked


def persist_alerts(conn, patient_id: str, actor_id: str | None, notify, uid, now) -> list[dict[str, Any]]:
    findings = evaluate_medications(conn, patient_id)
    stored = []
    for item in findings:
        existing = conn.execute(
            """SELECT id,status FROM medication_alerts
               WHERE patient_id=? AND alert_type=? AND COALESCE(medication_a,'')=COALESCE(?,'')
                 AND COALESCE(medication_b,'')=COALESCE(?,'') AND status IN ('NEW','REVIEWED')""",
            (patient_id, item["alert_type"], item["medication_a"], item["medication_b"]),
        ).fetchone()
        if existing:
            row = dict(conn.execute("SELECT * FROM medication_alerts WHERE id=?", (existing["id"],)).fetchone())
            stored.append(row)
            continue
        alert_id = uid("malert")
        stamp = now()
        conn.execute(
            """INSERT INTO medication_alerts
               (id,patient_id,alert_type,severity,medication_a,medication_b,doctor_a,doctor_b,explanation,recommended_action,status,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (alert_id, patient_id, item["alert_type"], item["severity"], item["medication_a"], item["medication_b"],
             item["doctor_a"], item["doctor_b"], item["explanation"], item["recommended_action"], "NEW", stamp, stamp),
        )
        row = dict(conn.execute("SELECT * FROM medication_alerts WHERE id=?", (alert_id,)).fetchone())
        stored.append(row)
        if item["severity"] in {"HIGH", "CRITICAL"}:
            message = (
                f"⚠ {'Critical' if item['severity']=='CRITICAL' else 'High'} Medication Interaction\n"
                f"Patient: {patient_id}\nMedication A: {item['medication_a']}\nMedication B: {item['medication_b'] or '—'}\n"
                "Please review this patient's medication combination."
            )
            for doctor_id in {item["doctor_a"], item["doctor_b"]} - {None}:
                user = conn.execute("SELECT user_id FROM doctors WHERE id=?", (doctor_id,)).fetchone()
                if user:
                    notify(conn, user_id=user["user_id"], kind="WARNING", message=message, related_type="medication_alert", related_id=alert_id)
            patient = conn.execute("SELECT user_id FROM patients WHERE id=?", (patient_id,)).fetchone()
            if patient:
                notify(conn, user_id=patient["user_id"], kind="WARNING",
                       message="A medication combination on your record requires clinician review. This is not a diagnosis.",
                       related_type="medication_alert", related_id=alert_id)
    return stored


def enrich_alert(conn, alert: dict[str, Any]) -> dict[str, Any]:
    patient = conn.execute("SELECT p.id,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?", (alert["patient_id"],)).fetchone()
    def doctor_label(doctor_id: str | None) -> dict[str, str] | None:
        if not doctor_id: return None
        row = conn.execute("SELECT d.id,d.specialty,u.name FROM doctors d JOIN users u ON u.id=d.user_id WHERE d.id=?", (doctor_id,)).fetchone()
        return dict(row) if row else None
    return {
        **alert,
        "patient_name": patient["name"] if patient else alert["patient_id"],
        "prescriber_a": doctor_label(alert.get("doctor_a")),
        "prescriber_b": doctor_label(alert.get("doctor_b")),
        "disclaimer": "Clinical decision support only. A clinician must review before any treatment change.",
    }


def emergency_summary(conn, patient_id: str, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    patient = conn.execute(
        "SELECT p.id,p.blood_type,p.allergies_json,p.conditions_json,p.medications_json,u.name FROM patients p JOIN users u ON u.id=p.user_id WHERE p.id=?",
        (patient_id,),
    ).fetchone()
    if not patient:
        return {}
    rx = active_prescriptions(conn, patient_id)
    critical = [item for item in alerts if item.get("severity") in {"HIGH", "CRITICAL"} and item.get("status") in {"NEW", "REVIEWED", None}]
    return {
        "patient": {"id": patient["id"], "name": patient["name"], "blood_type": patient["blood_type"]},
        "allergies": json.loads(patient["allergies_json"] or "[]"),
        "medications": [{"name": item["medication_name"], "dosage": item["dosage"], "prescriber": item["doctor_name"], "specialty": item["specialty"]} for item in rx]
        or json.loads(patient["medications_json"] or "[]"),
        "chronic_conditions": json.loads(patient["conditions_json"] or "[]"),
        "critical_warnings": [
            {"severity": item.get("severity"), "type": item.get("alert_type"), "detail": item.get("explanation")}
            for item in critical[:6]
        ],
        "disclaimer": "Emergency snapshot for immediate care. Not a complete record and not a diagnosis.",
    }


def active_break_glass(conn, actor_id: str, patient_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT * FROM emergency_access
           WHERE actor_id=? AND patient_id=? AND revoked_at IS NULL AND expires_at>?
           ORDER BY started_at DESC""",
        (actor_id, patient_id, iso()),
    ).fetchone()
    return dict(row) if row else None


def open_break_glass(conn, actor_id: str, patient_id: str, reason: str, device: str | None, uid) -> dict[str, Any]:
    started = utcnow()
    expires = started + timedelta(minutes=BREAK_GLASS_MINUTES)
    access_id = uid("glass")
    conn.execute(
        "INSERT INTO emergency_access VALUES(?,?,?,?,?,?,?,?)",
        (access_id, actor_id, patient_id, reason, device, iso(started), iso(expires), None),
    )
    return dict(conn.execute("SELECT * FROM emergency_access WHERE id=?", (access_id,)).fetchone())


def hospital_snapshot(conn) -> list[dict[str, Any]]:
    rows = [dict(item) for item in conn.execute(
        """SELECT h.id,h.name,h.city,o.latitude,o.longitude,o.er_load_percent,o.icu_total,o.icu_available,
                  o.available_beds,o.ambulances,o.avg_wait_minutes,o.specialties,o.equipment
           FROM hospital_ops o JOIN hospitals h ON h.id=o.hospital_id"""
    ).fetchall()]
    for item in rows:
        item["load"] = load_band(item["er_load_percent"])
        item["specialties"] = item["specialties"].split(",")
        item["equipment"] = item["equipment"].split(",")
    return rows


def recommend_hospital(conn, *, origin_lat: float, origin_lng: float, severity: str, required_specialty: str | None, needs_icu: bool, equipment: str | None = None) -> dict[str, Any]:
    options = []
    for hospital in hospital_snapshot(conn):
        distance = haversine_km(origin_lat, origin_lng, hospital["latitude"], hospital["longitude"])
        minutes = travel_minutes(distance)
        specialty_ok = (not required_specialty) or required_specialty.lower() in {x.lower() for x in hospital["specialties"]}
        equipment_ok = (not equipment) or equipment.lower() in {x.lower() for x in hospital["equipment"]}
        icu_ok = (not needs_icu) or hospital["icu_available"] > 0
        score = (
            hospital["available_beds"] * 2
            + hospital["icu_available"] * 12
            - hospital["er_load_percent"] * 0.45
            - distance * 3.2
            - hospital["avg_wait_minutes"] * 0.15
            + (18 if specialty_ok else -40)
            + (8 if equipment_ok else 0)
            + (25 if icu_ok and needs_icu else 0)
            - (80 if needs_icu and hospital["icu_available"] == 0 else 0)
            - (30 if hospital["er_load_percent"] >= 95 else 0)
        )
        if severity == "CRITICAL" and hospital["icu_available"] == 0 and needs_icu:
            score -= 50
        options.append({**hospital, "distance_km": distance, "travel_minutes": minutes, "specialty_match": specialty_ok, "icu_ok": icu_ok, "score": round(score, 1)})
    ranked = sorted(options, key=lambda x: (-x["score"], x["distance_km"]))
    capable = [item for item in ranked if item["icu_ok"] and item["specialty_match"]]
    if needs_icu and severity in {"HIGH", "CRITICAL"} and capable:
        chosen = min(capable, key=lambda x: x["distance_km"])
    else:
        chosen = capable[0] if capable else (ranked[0] if ranked else None)
    if not chosen:
        return {"recommended": None, "alternatives": [], "disclaimer": "No hospital snapshot is configured."}
    reasons = []
    if chosen["icu_ok"] and needs_icu: reasons.append(f"ICU available ({chosen['icu_available']} beds)")
    if chosen["specialty_match"] and required_specialty: reasons.append(f"{required_specialty} capability")
    reasons.append(f"{chosen['distance_km']} km distance")
    reasons.append(f"Estimated travel time: {chosen['travel_minutes']} min")
    reasons.append(f"Emergency department load {chosen['er_load_percent']}% ({chosen['load']})")
    return {
        "recommended": chosen,
        "reasons": reasons,
        "priority": "HIGH" if severity in {"HIGH", "CRITICAL"} else "MEDIUM",
        "alternatives": ranked[1:4],
        "disclaimer": "Routing support for an emergency operator. Destination choice remains a clinical and operational decision.",
    }


def match_blood(conn, *, requesting_hospital_id: str, blood_type: str, units_needed: int) -> list[dict[str, Any]]:
    origin = conn.execute("SELECT * FROM hospital_ops WHERE hospital_id=?", (requesting_hospital_id,)).fetchone()
    if not origin: return []
    matches = []
    for row in conn.execute(
        """SELECT b.*,h.name hospital_name,o.latitude,o.longitude
           FROM blood_inventory b JOIN hospitals h ON h.id=b.hospital_id JOIN hospital_ops o ON o.hospital_id=b.hospital_id
           WHERE b.blood_type=? AND b.units>0 AND b.hospital_id!=?""",
        (blood_type, requesting_hospital_id),
    ).fetchall():
        item = dict(row)
        distance = haversine_km(origin["latitude"], origin["longitude"], item["latitude"], item["longitude"])
        matches.append({
            "hospital_id": item["hospital_id"],
            "hospital_name": item["hospital_name"],
            "blood_type": blood_type,
            "units": item["units"],
            "distance_km": distance,
            "travel_minutes": travel_minutes(distance),
            "covers_request": item["units"] >= units_needed,
            "priority": "CRITICAL" if units_needed >= 4 else "HIGH",
        })
    return sorted(matches, key=lambda x: (0 if x["covers_request"] else 1, x["distance_km"]))


def epidemic_from_reports(conn) -> list[dict[str, Any]]:
    """Compare the last 7 days with the prior 7 days. Never claims a pandemic."""
    today = utcnow().date()
    signals = []
    regions = [row["region"] for row in conn.execute("SELECT DISTINCT region FROM symptom_reports").fetchall()]
    for region in regions:
        recent = [dict(row) for row in conn.execute(
            "SELECT symptom,SUM(count) total FROM symptom_reports WHERE region=? AND report_date>=? GROUP BY symptom",
            (region, (today - timedelta(days=7)).isoformat()),
        ).fetchall()]
        baseline = {row["symptom"]: row["total"] for row in conn.execute(
            "SELECT symptom,SUM(count) total FROM symptom_reports WHERE region=? AND report_date<? AND report_date>=? GROUP BY symptom",
            (region, (today - timedelta(days=7)).isoformat(), (today - timedelta(days=14)).isoformat()),
        ).fetchall()}
        shifts = []
        for item in recent:
            previous = baseline.get(item["symptom"]) or max(item["total"] / 2, 1)
            change = round((item["total"] - previous) / previous * 100, 1)
            shifts.append({"symptom": item["symptom"], "recent": item["total"], "baseline": previous, "change_percent": change})
        if not shifts:
            continue
        peak = max(shifts, key=lambda x: x["change_percent"])
        if peak["change_percent"] < 15:
            continue
        risk = "HIGH" if peak["change_percent"] >= 40 else "MEDIUM" if peak["change_percent"] >= 25 else "LOW"
        confidence = min(0.95, 0.55 + peak["change_percent"] / 100)
        respiratory = any(x["symptom"] in {"cough", "respiratory", "fever"} and x["change_percent"] >= 15 for x in shifts)
        signal = "Unusual respiratory symptom activity" if respiratory else "Unusual symptom activity"
        signals.append({
            "region": region,
            "signal": signal,
            "change_percent": peak["change_percent"],
            "confidence": round(confidence, 2),
            "risk": risk,
            "symptoms": shifts,
            "recommendation": "Requires epidemiological review. This is a potential outbreak signal, not a confirmed outbreak.",
        })
    return signals
