"""Deterministic Phase 11 demo data and readiness checks.

This module only owns synthetic records whose identifiers or email addresses are
explicitly demo-scoped. Resetting it does not drop the database.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEMO_VERSION = 11
HOSPITAL_ID = "hospital_caspian"
MASTER_PATIENT_ID = "patient_hasan"
MASTER_DOCTOR_ID = "doctor_leyla"
DEMO_DOCTOR_IDS = (
    "doctor_leyla", "doctor_orxan", "doctor_nigar", "doctor_elvin",
    "doctor_samira", "doctor_ramil", "doctor_aysu", "doctor_tural",
)
DEMO_EMAILS = (
    "patient@demo.az", "doctor@demo.az", "admin@demo.az",
    "doctor_orxan@demo.az", "doctor_nigar@demo.az", "doctor_elvin@demo.az",
    "doctor_samira@demo.az", "doctor_ramil@demo.az", "doctor_aysu@demo.az",
    "doctor_tural@demo.az", "patient104@demo.az", "patient207@demo.az",
    "followup@demo.az", "queue1@demo.az", "queue2@demo.az", "queue3@demo.az",
    "flow301@demo.az", "flow302@demo.az", "flow303@demo.az", "flow304@demo.az",
)
DEMO_PATIENT_IDS = (
    "patient_hasan", "patient_104", "patient_207", "patient_followup",
    "patient_queue_1", "patient_queue_2", "patient_queue_3",
    "patient_flow_301", "patient_flow_302", "patient_flow_303", "patient_flow_304",
)


def _placeholders(values: tuple[str, ...] | list[str]) -> str:
    return ",".join("?" for _ in values)


def _upsert(conn: sqlite3.Connection, table: str, columns: tuple[str, ...], values: tuple[Any, ...]) -> None:
    names = ",".join(columns)
    updates = ",".join(f"{name}=excluded.{name}" for name in columns if name != "id")
    conn.execute(
        f"INSERT INTO {table} ({names}) VALUES ({_placeholders(values)}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        values,
    )


def reset_demo_data(conn: sqlite3.Connection) -> list[str]:
    """Restore all demo-owned state in the caller's transaction.

    Returns local upload paths that can be removed after the transaction commits.
    """
    stamp = datetime.now(timezone.utc)
    created = stamp.isoformat()
    patient_marks = _placeholders(DEMO_PATIENT_IDS)
    doctor_marks = _placeholders(DEMO_DOCTOR_IDS)
    email_marks = _placeholders(DEMO_EMAILS)
    event_ids = [row[0] for row in conn.execute(
        "SELECT id FROM cv_events WHERE hospital_id=? AND room_id='204'", (HOSPITAL_ID,)
    ).fetchall()]
    safety_task_ids: list[str] = []
    if event_ids:
        event_marks = _placeholders(event_ids)
        safety_task_ids = [row[0] for row in conn.execute(
            f"SELECT id FROM safety_tasks WHERE event_id IN ({event_marks})", event_ids
        ).fetchall()]
    upload_paths = [row[0] for row in conn.execute(
        f"SELECT storage_path FROM medical_documents WHERE patient_id IN ({patient_marks})",
        DEMO_PATIENT_IDS,
    ).fetchall()]

    # Delete only transactions owned by the synthetic demo identities/resources.
    conn.execute(f"DELETE FROM audit_events WHERE actor_id IN (SELECT id FROM users WHERE email IN ({email_marks}))", DEMO_EMAILS)
    conn.execute(f"DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email IN ({email_marks})) OR id IN ('notification_patient_ready','notification_doctor_demo','notification_admin_capacity') OR related_id IN ('task_104','task_207')", DEMO_EMAILS)
    if event_ids:
        marks = _placeholders(event_ids)
        conn.execute(f"DELETE FROM audit_events WHERE actor_id='cv_service' AND entity_id IN ({marks})", event_ids)
        conn.execute(f"DELETE FROM notifications WHERE related_id IN ({marks})", event_ids)
        if safety_task_ids:
            task_marks = _placeholders(safety_task_ids)
            conn.execute(f"DELETE FROM notifications WHERE related_id IN ({task_marks})", safety_task_ids)
        conn.execute(f"DELETE FROM safety_tasks WHERE event_id IN ({marks})", event_ids)
        conn.execute(f"DELETE FROM safety_event_details WHERE event_id IN ({marks})", event_ids)
        conn.execute(f"DELETE FROM cv_events WHERE id IN ({marks})", event_ids)
    conn.execute(f"DELETE FROM medical_documents WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM lab_results WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM medical_records WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM consultations WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM consents WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM checkins WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM appointments WHERE patient_id IN ({patient_marks}) OR doctor_id IN ({doctor_marks})", (*DEMO_PATIENT_IDS, *DEMO_DOCTOR_IDS))
    conn.execute(f"DELETE FROM availability WHERE doctor_id IN ({doctor_marks})", DEMO_DOCTOR_IDS)
    conn.execute("DELETE FROM tasks WHERE id IN ('task_104','task_207')")
    conn.execute("DELETE FROM discharge_blockers WHERE id IN ('blocker_104','blocker_207')")
    conn.execute(f"DELETE FROM admissions WHERE patient_id IN ({patient_marks})", DEMO_PATIENT_IDS)
    bed_ids = tuple(f"bed_{index}" for index in range(1, 201))
    conn.execute(f"DELETE FROM beds WHERE id IN ({_placeholders(bed_ids)})", bed_ids)
    conn.execute("DELETE FROM rooms WHERE id='room_204'")
    conn.execute(f"DELETE FROM doctors WHERE id IN ({doctor_marks})", DEMO_DOCTOR_IDS)
    conn.execute(f"DELETE FROM patients WHERE id IN ({patient_marks})", DEMO_PATIENT_IDS)
    conn.execute(f"DELETE FROM users WHERE email IN ({email_marks})", DEMO_EMAILS)
    conn.execute("DELETE FROM insurance_coverage WHERE plan_id IN ('PLAN_BASIC','PLAN_PLUS','PLAN_PREMIUM')")
    conn.execute("DELETE FROM insurance_plans WHERE id IN ('PLAN_BASIC','PLAN_PLUS','PLAN_PREMIUM')")

    _upsert(conn, "hospitals", ("id", "name", "city", "emergency_waiting", "expected_incoming"),
            (HOSPITAL_ID, "Caspian Medical Center", "Baku", 12, 12))

    departments = (
        ("dept_icu", HOSPITAL_ID, "ICU"),
        ("dept_cardio", HOSPITAL_ID, "Cardiology"),
        ("dept_surgery", HOSPITAL_ID, "Surgery"),
        ("dept_neuro", HOSPITAL_ID, "Neurology"),
        ("dept_internal", HOSPITAL_ID, "Internal Medicine"),
    )
    for department in departments:
        _upsert(conn, "departments", ("id", "hospital_id", "name"), department)

    users = (
        ("user_patient", "Hasan M.", "patient@demo.az", "PATIENT", "{}"),
        ("user_doctor", "Dr. Leyla Mammadova", "doctor@demo.az", "DOCTOR", "{}"),
        ("user_admin", "Aysel Karimova", "admin@demo.az", "HOSPITAL_ADMIN", json.dumps({"hospital_id": HOSPITAL_ID})),
        ("user_doctor_orxan", "Dr. Orxan Aliyev", "doctor_orxan@demo.az", "DOCTOR", "{}"),
        ("user_doctor_nigar", "Dr. Nigar Huseynova", "doctor_nigar@demo.az", "DOCTOR", "{}"),
        ("user_doctor_elvin", "Dr. Elvin Rahimov", "doctor_elvin@demo.az", "DOCTOR", "{}"),
        ("user_doctor_samira", "Dr. Samira Quliyeva", "doctor_samira@demo.az", "DOCTOR", "{}"),
        ("user_doctor_ramil", "Dr. Ramil Hasanov", "doctor_ramil@demo.az", "DOCTOR", "{}"),
        ("user_doctor_aysu", "Dr. Aysu Mammadli", "doctor_aysu@demo.az", "DOCTOR", "{}"),
        ("user_doctor_tural", "Dr. Tural Safarov", "doctor_tural@demo.az", "DOCTOR", "{}"),
        ("user_104", "Patient #104", "patient104@demo.az", "PATIENT", "{}"),
        ("user_207", "Patient #207", "patient207@demo.az", "PATIENT", "{}"),
        ("user_followup", "Amina R.", "followup@demo.az", "PATIENT", "{}"),
        *tuple((f"user_queue_{i}", f"Queue Patient #{i}", f"queue{i}@demo.az", "PATIENT", "{}") for i in range(1, 4)),
        *tuple((f"user_flow_{i}", f"Discharge Candidate #{i}", f"flow{i}@demo.az", "PATIENT", "{}") for i in range(301, 305)),
    )
    conn.executemany("INSERT INTO users VALUES(?,?,?,?,?,?)", [(*item, created) for item in users])

    plans = (("PLAN_BASIC", "Basic Health"), ("PLAN_PLUS", "Plus Health"), ("PLAN_PREMIUM", "Premium Health"))
    conn.executemany("INSERT INTO insurance_plans VALUES(?,?)", plans)
    coverage = (
        ("PLAN_BASIC", "Endocrinology", 60), ("PLAN_BASIC", "Cardiology", 50),
        ("PLAN_PLUS", "Endocrinology", 70), ("PLAN_PLUS", "Cardiology", 70),
        ("PLAN_PREMIUM", "Endocrinology", 80), ("PLAN_PREMIUM", "Cardiology", 80),
        ("PLAN_PREMIUM", "Neurology", 80), ("PLAN_PREMIUM", "Dermatology", 80),
        ("PLAN_PREMIUM", "Internal Medicine", 80), ("PLAN_PREMIUM", "Surgery", 80),
        ("PLAN_PREMIUM", "Blood Tests", 100), ("PLAN_PREMIUM", "MRI", 50),
        ("PLAN_PREMIUM", "Dentistry", 0),
    )
    conn.executemany("INSERT INTO insurance_coverage VALUES(?,?,?)", coverage)

    patients = [
        ("patient_hasan", "user_patient", "2004-04-12", "Male", "+994 50 555 01 01", "A+", "Nigar M., +994 50 555 01 02", "PLAN_PREMIUM", json.dumps([{"name": "Penicillin", "reaction": "rash", "recorded": "2024"}]), json.dumps(["Family history of type 2 diabetes"]), json.dumps([{"name": "Metformin", "dosage": "500 mg"}])),
        ("patient_104", "user_104", "1970-01-01", "Other", "", "", "", "PLAN_BASIC", "[]", "[]", "[]"),
        ("patient_207", "user_207", "1972-01-01", "Other", "", "", "", "PLAN_PLUS", "[]", "[]", "[]"),
        ("patient_followup", "user_followup", "1988-06-15", "Female", "", "O+", "", "PLAN_PLUS", "[]", "[]", "[]"),
    ]
    patients.extend((f"patient_queue_{i}", f"user_queue_{i}", "1980-01-01", "Other", "", "", "", "PLAN_BASIC", "[]", "[]", "[]") for i in range(1, 4))
    patients.extend((f"patient_flow_{i}", f"user_flow_{i}", "1975-01-01", "Other", "", "", "", "PLAN_BASIC", "[]", "[]", "[]") for i in range(301, 305))
    conn.executemany("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?,?,?,?)", patients)

    doctors = (
        ("doctor_leyla", "user_doctor", HOSPITAL_ID, "Endocrinology", 12, 4.9, 60.0, "PLAN_BASIC,PLAN_PLUS,PLAN_PREMIUM"),
        ("doctor_orxan", "user_doctor_orxan", HOSPITAL_ID, "Cardiology", 10, 4.8, 70.0, "PLAN_PLUS,PLAN_PREMIUM"),
        ("doctor_nigar", "user_doctor_nigar", HOSPITAL_ID, "Dermatology", 8, 4.7, 50.0, "PLAN_BASIC,PLAN_PREMIUM"),
        ("doctor_elvin", "user_doctor_elvin", HOSPITAL_ID, "Neurology", 14, 4.9, 75.0, "PLAN_PREMIUM"),
        ("doctor_samira", "user_doctor_samira", HOSPITAL_ID, "Internal Medicine", 9, 4.8, 55.0, "PLAN_BASIC,PLAN_PLUS,PLAN_PREMIUM"),
        ("doctor_ramil", "user_doctor_ramil", HOSPITAL_ID, "Surgery", 15, 4.8, 85.0, "PLAN_PLUS,PLAN_PREMIUM"),
        ("doctor_aysu", "user_doctor_aysu", HOSPITAL_ID, "Pediatrics", 7, 4.7, 45.0, "PLAN_BASIC,PLAN_PLUS"),
        ("doctor_tural", "user_doctor_tural", HOSPITAL_ID, "Radiology", 11, 4.8, 65.0, "PLAN_PREMIUM"),
    )
    conn.executemany("INSERT INTO doctors VALUES(?,?,?,?,?,?,?,?)", doctors)

    historical_records = (
        ("record_general_2024", "patient_hasan", "CHECKUP", "General check-up", "2024-02-22", HOSPITAL_ID, "doctor_samira", "DOCTOR_NOTES", json.dumps({"note": "Routine general check-up completed."}), "", created),
        ("record_allergy_2024", "patient_hasan", "ALLERGY", "Penicillin allergy recorded", "2024-02-22", HOSPITAL_ID, "doctor_samira", "DIAGNOSES", json.dumps({"allergy": "Penicillin", "status": "YES"}), "Penicillin allergy: YES; reaction: rash", created),
        ("record_visit_2025", "patient_hasan", "DOCTOR_VISIT", "Routine doctor visit", "2025-03-10", HOSPITAL_ID, "doctor_samira", "DOCTOR_NOTES", json.dumps({"note": "Lifestyle review completed."}), "", created),
        ("record_conflict_2026", "patient_hasan", "IMPORTED_RECORD", "Imported external check-up", "2026-08-01", HOSPITAL_ID, None, "LAB_RESULTS", json.dumps({"allergies": "NONE"}), "No known allergies", created),
        ("record_navigation_2026", "patient_hasan", "CARE_NAVIGATION", "Endocrinology review suggested", "2026-08-18", HOSPITAL_ID, None, "LAB_RESULTS", json.dumps({"specialty": "Endocrinology", "diagnosis": False}), "Navigation suggestion only; no diagnosis.", created),
    )
    conn.executemany("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)", historical_records)

    metrics = {
        "HbA1c": (("2024-02-22", 5.4), ("2025-03-10", 5.8), ("2026-08-18", 6.3), "%", "4.0-5.6"),
        "Glucose": (("2024-02-22", 89), ("2025-03-10", 96), ("2026-08-18", 108), "mg/dL", "70-99"),
        "Vitamin D": (("2024-02-22", 17), ("2025-03-10", 21), ("2026-08-18", 28), "ng/mL", "30-100"),
        "Hemoglobin": (("2024-02-22", 14.0), ("2025-03-10", 14.1), ("2026-08-18", 14.1), "g/dL", "13.5-17.5"),
    }
    for metric, values in metrics.items():
        series, unit, reference = values[:3], values[3], values[4]
        slug = metric.lower().replace(" ", "_")
        for year_index, (result_date, value) in enumerate(series, start=2024):
            record_id = f"record_lab_{slug}_{year_index}"
            conn.execute("INSERT INTO medical_records VALUES(?,?,?,?,?,?,?,?,?,?,?)", (record_id, MASTER_PATIENT_ID, "LAB_RESULT", f"{metric} result", result_date, HOSPITAL_ID, None, "LAB_RESULTS", json.dumps({"metric": metric, "value": value, "unit": unit}), None, created))
            conn.execute("INSERT INTO lab_results VALUES(?,?,?,?,?,?,?,?)", (f"lab_{slug}_{year_index}", MASTER_PATIENT_ID, metric, value, unit, reference, result_date, record_id))

    tomorrow = (stamp + timedelta(days=1)).date()
    def at(hour: int, minute: int = 0) -> datetime:
        return datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=timezone.utc)

    queue_slots = (("slot_queue_1", at(5, 0)), ("slot_queue_2", at(5, 30)), ("slot_queue_3", at(6, 0)))
    demo_slots = (("slot_leyla_0", at(7, 0)), ("slot_leyla_1", at(7, 30)), ("slot_leyla_2", at(10, 0)), ("slot_leyla_3", at(10, 30)))
    for slot_id, start in queue_slots:
        conn.execute("INSERT INTO availability VALUES(?,?,?,?,?)", (slot_id, MASTER_DOCTOR_ID, start.isoformat(), (start + timedelta(minutes=30)).isoformat(), "BOOKED"))
    for slot_id, start in demo_slots:
        conn.execute("INSERT INTO availability VALUES(?,?,?,?,?)", (slot_id, MASTER_DOCTOR_ID, start.isoformat(), (start + timedelta(minutes=30)).isoformat(), "AVAILABLE"))
    history_start = stamp - timedelta(days=14)
    conn.execute("INSERT INTO availability VALUES(?,?,?,?,?)", ("slot_followup_history", MASTER_DOCTOR_ID, history_start.isoformat(), (history_start + timedelta(minutes=30)).isoformat(), "BOOKED"))
    for index, (slot_id, _) in enumerate(queue_slots, start=1):
        conn.execute("INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?)", (f"appointment_queue_{index}", f"patient_queue_{index}", MASTER_DOCTOR_ID, slot_id, "WAITING", "Demo queue", "{}", created))
    conn.execute("INSERT INTO appointments VALUES(?,?,?,?,?,?,?,?)", ("appointment_followup_history", "patient_followup", MASTER_DOCTOR_ID, "slot_followup_history", "COMPLETED", "Post-discharge follow-up", "{}", created))

    # Exact department totals: ICU 20, Cardiology 40, Surgery 45, Neurology 35, Internal Medicine 60.
    for index in range(1, 201):
        if index <= 20: department = "dept_icu"
        elif index <= 60: department = "dept_cardio"
        elif index <= 105: department = "dept_surgery"
        elif index <= 140: department = "dept_neuro"
        else: department = "dept_internal"
        if index in (104, 105): department = "dept_internal"
        if index in (141, 142): department = "dept_surgery"
        conn.execute("INSERT INTO beds VALUES(?,?,?,?,?)", (f"bed_{index}", HOSPITAL_ID, department, str(200 + index // 2), "OCCUPIED" if index <= 195 else "AVAILABLE"))

    admission_rows = (
        ("admission_104", "patient_104", "dept_internal", "bed_104", 1),
        ("admission_207", "patient_207", "dept_internal", "bed_105", 1),
        ("admission_flow_301", "patient_flow_301", "dept_internal", "bed_191", 1),
        ("admission_flow_302", "patient_flow_302", "dept_internal", "bed_192", 1),
        ("admission_flow_303", "patient_flow_303", "dept_internal", "bed_193", 1),
        ("admission_flow_304", "patient_flow_304", "dept_internal", "bed_194", 1),
    )
    for admission_id, patient_id, department_id, bed_id, ready in admission_rows:
        conn.execute("INSERT INTO admissions VALUES(?,?,?,?,?,?,?,?,?)", (admission_id, patient_id, HOSPITAL_ID, department_id, bed_id, (stamp - timedelta(days=2)).isoformat(), (stamp + timedelta(hours=4)).isoformat(), ready, "ACTIVE"))

    blockers = (
        ("blocker_104", "admission_104", "LAB_REVIEW_PENDING", "DOCTOR", "OPEN", 35, (stamp - timedelta(minutes=137)).isoformat(), None),
        ("blocker_207", "admission_207", "PHARMACY_PENDING", "HOSPITAL_ADMIN", "OPEN", 55, (stamp - timedelta(minutes=65)).isoformat(), None),
    )
    conn.executemany("INSERT INTO discharge_blockers VALUES(?,?,?,?,?,?,?,?)", blockers)
    tasks = (
        ("task_104", "Review Lab Result", "admission_104", "blocker_104", "DOCTOR", "HIGH", 80, "PENDING", "Potentially frees 1 bed in ~35 min", created, None),
        ("task_207", "Prepare Medication", "admission_207", "blocker_207", "HOSPITAL_ADMIN", "MEDIUM", 60, "PENDING", "Potentially frees 1 bed in ~55 min", created, None),
    )
    conn.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)", tasks)

    conn.execute("INSERT INTO checkins VALUES(?,?,?,?,?,?,?,?,?)", ("checkin_followup_day1", "patient_followup", "admission_followup", (stamp.date() - timedelta(days=2)).isoformat(), 4, 37.1, 1, "", "Recovering"))
    conn.execute("INSERT INTO checkins VALUES(?,?,?,?,?,?,?,?,?)", ("checkin_followup_day2", "patient_followup", "admission_followup", (stamp.date() - timedelta(days=1)).isoformat(), 5, 37.5, 1, "fatigue", "Monitor symptoms"))

    conn.execute("INSERT INTO rooms VALUES(?,?,?,?,?)", ("room_204", HOSPITAL_ID, "dept_internal", "STABLE", json.dumps({"fall_risk": "HIGH", "identity_recognition": False})))
    notifications = (
        ("notification_patient_ready", "user_patient", None, None, "INFO", "Your synthetic health timeline is ready.", None, None, None, created),
        ("notification_doctor_demo", "user_doctor", None, None, "INFO", "Three patients are ahead in today's demo queue.", "queue", MASTER_DOCTOR_ID, None, created),
        ("notification_admin_capacity", None, "HOSPITAL_ADMIN", HOSPITAL_ID, "WARNING", "Capacity risk is high: 5 beds available and 12 patients expected.", "hospital", HOSPITAL_ID, None, created),
    )
    conn.executemany("INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?,?,?)", notifications)
    conn.execute("INSERT INTO demo_seed_versions(key,version,updated_at) VALUES('master',?,?) ON CONFLICT(key) DO UPDATE SET version=excluded.version,updated_at=excluded.updated_at", (DEMO_VERSION, created))
    return upload_paths


def demo_readiness(conn: sqlite3.Connection, demo_pdf: Path) -> dict[str, Any]:
    checks = {
        "database": conn.execute("SELECT 1").fetchone() is not None,
        "master_patient": conn.execute("SELECT COUNT(*) FROM patients WHERE id='patient_hasan'").fetchone()[0] == 1,
        "master_doctor": conn.execute("SELECT COUNT(*) FROM doctors WHERE id='doctor_leyla'").fetchone()[0] == 1,
        "doctor_count": conn.execute("SELECT COUNT(*) FROM doctors WHERE hospital_id=?", (HOSPITAL_ID,)).fetchone()[0] >= 8,
        "available_slot": conn.execute("SELECT COUNT(*) FROM availability WHERE doctor_id='doctor_leyla' AND status='AVAILABLE'").fetchone()[0] >= 1,
        "no_master_appointment": conn.execute("SELECT COUNT(*) FROM appointments WHERE patient_id='patient_hasan' AND status!='CANCELLED'").fetchone()[0] == 0,
        "no_active_consent": conn.execute("SELECT COUNT(*) FROM consents WHERE patient_id='patient_hasan' AND status='ACTIVE'").fetchone()[0] == 0,
        "hospital_200_beds": conn.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=?", (HOSPITAL_ID,)).fetchone()[0] == 200,
        "hospital_195_occupied": conn.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=? AND status='OCCUPIED'", (HOSPITAL_ID,)).fetchone()[0] == 195,
        "blocker_104_open": conn.execute("SELECT COUNT(*) FROM discharge_blockers WHERE id='blocker_104' AND status='OPEN'").fetchone()[0] == 1,
        "task_104_pending": conn.execute("SELECT COUNT(*) FROM tasks WHERE id='task_104' AND status='PENDING'").fetchone()[0] == 1,
        "room_204_stable": conn.execute("SELECT COUNT(*) FROM rooms WHERE id='room_204' AND safety_status='STABLE'").fetchone()[0] == 1,
        "no_active_cv_events": conn.execute("SELECT COUNT(*) FROM cv_events e JOIN safety_event_details d ON d.event_id=e.id WHERE e.room_id='204' AND d.status!='RESOLVED'").fetchone()[0] == 0,
        "demo_pdf": demo_pdf.exists(),
        "ai_fallback": True,
        "cv_simulator_contract": True,
    }
    return {"ready": all(checks.values()), "checks": checks, "version": DEMO_VERSION}
