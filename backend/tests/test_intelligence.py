import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app, DB_PATH


def reset():
    if DB_PATH.exists(): DB_PATH.unlink()
    from app.main import seed
    seed()


def client():
    reset()
    return TestClient(app)


def test_drug_interaction_detection():
    c = client()
    doctor = {"X-Demo-User": "doctor@demo.az"}
    alerts = c.get("/medication-alerts", headers=doctor).json()
    types = {item["alert_type"] for item in alerts if item["patient_id"] == "patient_hasan"}
    assert "DRUG_DRUG" in types
    pair = next(item for item in alerts if item["alert_type"] == "DRUG_DRUG" and item["patient_id"] == "patient_hasan")
    names = {pair["medication_a"], pair["medication_b"]}
    assert names == {"Lisinopril", "Ibuprofen"}
    assert pair["severity"] == "HIGH"
    assert c.get("/notifications", headers=doctor).json()


def test_duplicate_medication_detection():
    c = client()
    doctor = {"X-Demo-User": "doctor@demo.az"}
    alerts = c.get("/medication-alerts", headers=doctor).json()
    same = [item for item in alerts if item["alert_type"] == "SAME_INGREDIENT" and item["patient_id"] == "patient_hasan"]
    assert same
    names = {same[0]["medication_a"], same[0]["medication_b"]}
    assert names == {"Metformin", "Glucophage"}


def test_allergy_conflict():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    alerts = c.get("/medication-alerts", headers=admin).json()
    allergy = next(item for item in alerts if item["patient_id"] == "patient_followup" and item["alert_type"] == "ALLERGY")
    assert allergy["severity"] == "CRITICAL"
    assert allergy["medication_a"] == "Amoxicillin"


def test_no_false_duplicate():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    alerts = c.get("/medication-alerts", headers=admin).json()
    false_dupes = [item for item in alerts if item["patient_id"] == "patient_207" and item["alert_type"] in {"DUPLICATE", "SAME_INGREDIENT"}]
    assert false_dupes == []


def test_break_glass_authorization():
    c = client()
    doctor = {"X-Demo-User": "doctor@demo.az"}
    patient = {"X-Demo-User": "patient@demo.az"}
    assert c.get("/emergency/summary/patient_hasan", headers={"X-Demo-User": "doctor_nigar@demo.az"}).status_code == 403
    opened = c.post("/emergency/break-glass", headers=doctor, json={"patient_id": "patient_hasan", "reason": "Patient unconscious"})
    assert opened.status_code == 200
    body = opened.json()
    assert body["reason"] == "Patient unconscious"
    summary = c.get("/emergency/summary/patient_hasan", headers=doctor).json()
    assert summary["patient"]["blood_type"] == "A+"
    assert any("Penicillin" in str(item) for item in summary["allergies"])
    assert summary["access"] == "BREAK_GLASS"
    own = c.get("/emergency/summary/patient_hasan", headers=patient).json()
    assert own["patient"]["id"] == "patient_hasan"


def test_break_glass_audit_log():
    c = client()
    doctor = {"X-Demo-User": "doctor@demo.az"}
    admin = {"X-Demo-User": "admin@demo.az"}
    c.post("/emergency/break-glass", headers=doctor, json={"patient_id": "patient_hasan", "reason": "Emergency treatment required"})
    trail = c.get("/audit", headers=admin).json()
    assert any(item["event_type"] == "BREAK_GLASS" for item in trail)


def test_emergency_summary():
    c = client()
    summary = c.get("/emergency/summary/patient_hasan", headers={"X-Demo-User": "patient@demo.az"}).json()
    meds = {item["name"] if isinstance(item, dict) else item for item in summary["medications"]}
    assert "Metformin" in meds and "Lisinopril" in meds
    assert summary["patient"]["name"]


def test_expired_break_glass_access():
    c = client()
    from app.main import db
    expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    started = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with db() as conn:
        conn.execute("INSERT INTO emergency_access VALUES(?,?,?,?,?,?,?,?)",
                     ("glass_expired", "user_doctor_nigar", "patient_hasan", "Patient unconscious", "test", started, expired, None))
    other = {"X-Demo-User": "doctor_nigar@demo.az"}
    assert c.get("/emergency/summary/patient_hasan", headers=other).status_code == 403


def test_hospital_recommendation():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    result = c.post("/hospitals/recommend", headers=admin, json={"severity": "CRITICAL", "required_specialty": "ICU", "needs_icu": True}).json()
    assert result["recommended"]["id"] == "hospital_absheron"
    assert result["recommended"]["icu_available"] == 4
    assert result["recommended"]["distance_km"] < result["alternatives"][0]["distance_km"] or result["alternatives"][0]["id"] != "hospital_caspian"


def test_icu_capacity():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    network = c.get("/hospitals/network", headers=admin).json()
    caspian = next(item for item in network if item["id"] == "hospital_caspian")
    absheron = next(item for item in network if item["id"] == "hospital_absheron")
    assert caspian["icu_available"] == 0 and caspian["load"] == "CRITICAL"
    assert absheron["icu_available"] == 4


def test_distance_priority():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    result = c.post("/hospitals/recommend", headers=admin, json={"severity": "CRITICAL", "needs_icu": True, "required_specialty": "ICU"}).json()
    chosen = result["recommended"]
    closer_full = next(item for item in c.get("/hospitals/network", headers=admin).json() if item["id"] == "hospital_caspian")
    assert chosen["id"] != "hospital_caspian"
    assert chosen["distance_km"] > 0
    assert closer_full["icu_available"] == 0


def test_blood_matching():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    matches = c.get("/resources/match", headers=admin, params={"blood_type": "O-", "units": 4}).json()
    assert matches[0]["hospital_id"] == "hospital_absheron"
    assert matches[0]["units"] >= 4
    created = c.post("/resource-matching", headers=admin, json={"blood_type": "O-", "units_needed": 4}).json()
    assert created["best"]["hospital_id"] == "hospital_absheron"


def test_resource_matching():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    created = c.post("/resource-matching", headers=admin, json={"resource_type": "BLOOD", "blood_type": "O-", "units_needed": 4, "priority": "CRITICAL"}).json()
    assert created["matches"]
    assert created["best"]["covers_request"] is True


def test_symptom_baseline():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    regions = c.get("/epidemics/regions", headers=admin).json()
    assert any(item["region"] == "Baku" and item["symptom"] == "respiratory" for item in regions)


def test_unusual_activity_detection():
    c = client()
    admin = {"X-Demo-User": "admin@demo.az"}
    signals = c.get("/epidemics/signals", headers=admin).json()
    baku = next(item for item in signals if item["region"] == "Baku")
    assert baku["change_percent"] >= 15
    assert "pandemic" not in baku["signal"].lower()
    assert "outbreak" in baku["recommendation"].lower() or "epidemiological" in baku["recommendation"].lower()


def test_intelligence_overview_and_patient_isolation():
    c = client()
    overview = c.get("/intelligence/overview", headers={"X-Demo-User": "admin@demo.az"}).json()
    assert overview["critical_medication_alerts"] >= 1
    assert overview["blood_resource_alerts"] >= 1
    other = {"X-Demo-User": "followup@demo.az"}
    assert c.get("/emergency/summary/patient_hasan", headers=other).status_code == 403
    assert c.get("/medication-alerts", headers={"X-Demo-User": "patient@demo.az"}).json()
    assert all(item["patient_id"] == "patient_hasan" for item in c.get("/medication-alerts", headers={"X-Demo-User": "patient@demo.az"}).json())
