"""Synthetic intelligence dataset restored with the rest of the demo seed."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .engines import persist_alerts

PARTNER_HOSPITALS = (
    ("hospital_absheron", "Absheron Medical Center", "Absheron"),
    ("hospital_nizami", "Nizami Emergency Hospital", "Baku"),
    ("hospital_sumgayit", "Sumgayit City Hospital", "Sumgayit"),
    ("hospital_ganja", "Ganja Regional Hospital", "Ganja"),
)


def reset_intelligence(conn: sqlite3.Connection) -> None:
    def uid(prefix: str) -> str: return f"{prefix}_{uuid4().hex[:12]}"
    def now() -> str: return datetime.now(timezone.utc).isoformat()
    def notify(conn, *, user_id=None, role=None, hospital_id=None, kind="INFO", message: str, related_type=None, related_id=None):
        conn.execute(
            "INSERT INTO notifications (id,user_id,role,hospital_id,type,message,related_type,related_id,read_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (uid("note"), user_id, role, hospital_id, kind, message, related_type, related_id, None, now()),
        )
    stamp = datetime.now(timezone.utc)
    created = stamp.isoformat()
    for table in (
        "resource_matches", "resource_requests", "blood_inventory", "epidemic_signals",
        "symptom_reports", "medication_alerts", "prescriptions", "medication_interactions",
        "medications", "emergency_access", "hospital_ops",
    ):
        conn.execute(f"DELETE FROM {table}")
    for hospital_id, name, city in PARTNER_HOSPITALS:
        conn.execute(
            "INSERT INTO hospitals (id,name,city,emergency_waiting,expected_incoming) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,city=excluded.city",
            (hospital_id, name, city, 4 if "ganja" not in hospital_id else 2, 6),
        )

    medications = (
        ("med_metformin", "Metformin", "metformin", "biguanide", 0, 2000),
        ("med_glucophage", "Glucophage", "metformin", "biguanide", 0, 2000),
        ("med_lisinopril", "Lisinopril", "lisinopril", "ace_inhibitor", 0, 40),
        ("med_ibuprofen", "Ibuprofen", "ibuprofen", "nsaid", 0, 2400),
        ("med_amoxicillin", "Amoxicillin", "amoxicillin", "penicillin", 1, None),
        ("med_warfarin", "Warfarin", "warfarin", "anticoagulant", 0, 10),
        ("med_aspirin", "Aspirin", "acetylsalicylic_acid", "antiplatelet", 0, 325),
        ("med_atorvastatin", "Atorvastatin", "atorvastatin", "statin", 0, 80),
        ("med_glipizide", "Glipizide", "glipizide", "sulfonylurea", 0, 20),
        ("med_losartan", "Losartan", "losartan", "arb", 0, 100),
        ("med_omeprazole", "Omeprazole", "omeprazole", "ppi", 0, 40),
        ("med_insulin", "Insulin glargine", "insulin_glargine", "insulin", 0, None),
        ("med_salbutamol", "Salbutamol", "salbutamol", "beta_agonist", 0, None),
        ("med_prednisone", "Prednisone", "prednisone", "corticosteroid", 0, 60),
        ("med_clopidogrel", "Clopidogrel", "clopidogrel", "antiplatelet", 0, 75),
        ("med_amlodipine", "Amlodipine", "amlodipine", "ccb", 0, 10),
        ("med_levothyroxine", "Levothyroxine", "levothyroxine", "thyroid", 0, 200),
        ("med_sertraline", "Sertraline", "sertraline", "ssri", 0, 200),
        ("med_metoprolol", "Metoprolol", "metoprolol", "beta_blocker", 0, 200),
        ("med_furosemide", "Furosemide", "furosemide", "loop_diuretic", 0, 80),
    )
    conn.executemany("INSERT INTO medications VALUES(?,?,?,?,?,?)", medications)

    interactions = (
        ("ix_ace_nsaid", "med_lisinopril", "med_ibuprofen", "DRUG_DRUG", "HIGH",
         "ACE inhibitors combined with NSAIDs may reduce renal perfusion and raise potassium. This is a clinically significant interaction signal.",
         "Review medication combination before continuation. Consider an alternative analgesic."),
        ("ix_warf_asp", "med_warfarin", "med_aspirin", "DRUG_DRUG", "CRITICAL",
         "Anticoagulant plus antiplatelet therapy increases bleeding risk.",
         "Urgent clinician review before both agents continue together."),
        ("ix_nsaid_warf", "med_ibuprofen", "med_warfarin", "DRUG_DRUG", "CRITICAL",
         "NSAIDs can increase anticoagulant effect and gastrointestinal bleeding risk.",
         "Avoid the combination unless a clinician documents a specific indication."),
        ("ix_statin_fibrate_placeholder", "med_atorvastatin", "med_glipizide", "DRUG_DRUG", "LOW",
         "No established major pharmacokinetic interaction in this demo knowledge base; residual monitoring is still appropriate in diabetes care.",
         "Continue routine metabolic monitoring."),
    )
    conn.executemany("INSERT INTO medication_interactions VALUES(?,?,?,?,?,?,?)", interactions)

    prescriptions = (
        ("rx_hasan_metformin", "patient_hasan", "doctor_leyla", "med_metformin", "500 mg twice daily", 1000, "ACTIVE", created, "Endocrinology"),
        ("rx_hasan_lisinopril", "patient_hasan", "doctor_orxan", "med_lisinopril", "10 mg daily", 10, "ACTIVE", created, "Cardiology"),
        ("rx_hasan_ibuprofen", "patient_hasan", "doctor_samira", "med_ibuprofen", "400 mg as needed", 400, "ACTIVE", created, "Family medicine / internal medicine"),
        ("rx_hasan_glucophage", "patient_hasan", "doctor_elvin", "med_glucophage", "500 mg daily", 500, "ACTIVE", created, "Overlapping diabetes therapy"),
        ("rx_followup_amox", "patient_followup", "doctor_samira", "med_amoxicillin", "500 mg three times daily", 500, "ACTIVE", created, "Allergy conflict demo"),
        ("rx_104_warfarin", "patient_104", "doctor_orxan", "med_warfarin", "5 mg daily", 5, "ACTIVE", created, ""),
        ("rx_104_aspirin", "patient_104", "doctor_samira", "med_aspirin", "81 mg daily", 81, "ACTIVE", created, ""),
        ("rx_207_statin", "patient_207", "doctor_orxan", "med_atorvastatin", "20 mg nightly", 20, "ACTIVE", created, ""),
        ("rx_207_metformin", "patient_207", "doctor_leyla", "med_metformin", "500 mg daily", 500, "ACTIVE", created, ""),
    )
    conn.executemany("INSERT INTO prescriptions VALUES(?,?,?,?,?,?,?,?,?)", prescriptions)
    conn.execute("UPDATE patients SET allergies_json=? WHERE id='patient_followup'",
                 ('[{"name":"Penicillin","reaction":"anaphylaxis","recorded":"2023"}]',))
    conn.execute(
        "UPDATE patients SET medications_json=?, conditions_json=? WHERE id='patient_hasan'",
        ('[{"name":"Metformin","dosage":"500 mg"},{"name":"Lisinopril","dosage":"10 mg"},{"name":"Ibuprofen","dosage":"400 mg"}]',
         '["Family history of type 2 diabetes","Hypertension"]'),
    )

    ops = (
        ("hospital_caspian", 40.4093, 49.8671, 98, 20, 0, 5, 3, 48, "ICU,Cardiology,Endocrinology,Surgery,Neurology,Internal Medicine", "ventilator,ct,dialysis"),
        ("hospital_absheron", 40.4720, 49.8671, 62, 12, 4, 14, 5, 18, "ICU,Cardiology,Emergency,Internal Medicine", "ventilator,ct"),
        ("hospital_nizami", 40.5170, 49.8671, 45, 16, 8, 22, 6, 12, "ICU,Emergency,Surgery,Pediatrics", "ventilator,ct,mri"),
        ("hospital_sumgayit", 40.589, 49.669, 71, 8, 1, 9, 4, 22, "ICU,Emergency,Internal Medicine", "ventilator"),
        ("hospital_ganja", 40.6828, 46.3606, 38, 10, 6, 18, 4, 15, "ICU,Emergency,Surgery,Cardiology", "ventilator,ct"),
    )
    conn.executemany("INSERT INTO hospital_ops VALUES(?,?,?,?,?,?,?,?,?,?,?)", ops)

    blood = (
        ("blood_caspian_aplus", "hospital_caspian", "A+", 6, created),
        ("blood_caspian_ominus", "hospital_caspian", "O-", 0, created),
        ("blood_absheron_ominus", "hospital_absheron", "O-", 8, created),
        ("blood_nizami_ominus", "hospital_nizami", "O-", 2, created),
        ("blood_sumgayit_ominus", "hospital_sumgayit", "O-", 1, created),
        ("blood_ganja_ominus", "hospital_ganja", "O-", 5, created),
        ("blood_absheron_aplus", "hospital_absheron", "A+", 10, created),
        ("blood_nizami_oneg", "hospital_nizami", "O+", 12, created),
    )
    conn.executemany("INSERT INTO blood_inventory VALUES(?,?,?,?,?)", blood)
    conn.execute(
        "INSERT INTO resource_requests VALUES(?,?,?,?,?,?,?,?)",
        ("req_caspian_ominus", "hospital_caspian", "BLOOD", "O-", 4, "CRITICAL", "OPEN", created),
    )

    symptoms = []
    baseline = {"fever": 40, "cough": 28, "fatigue": 22, "respiratory": 30}
    recent = {"fever": 45, "cough": 33, "fatigue": 24, "respiratory": 37}
    baku_recent = {"fever": 45, "cough": 33, "fatigue": 24, "respiratory": 42}
    for day in range(14, 7, -1):
        date = (stamp.date() - timedelta(days=day)).isoformat()
        for symptom, count in baseline.items():
            symptoms.append((f"sym_baku_{symptom}_{day}", "Baku", symptom, count, date))
            symptoms.append((f"sym_ganja_{symptom}_{day}", "Ganja", symptom, count - 8, date))
    for day in range(7, 0, -1):
        date = (stamp.date() - timedelta(days=day)).isoformat()
        for symptom, count in baku_recent.items():
            symptoms.append((f"sym_baku_{symptom}_{day}", "Baku", symptom, count, date))
        for symptom, count in recent.items():
            symptoms.append((f"sym_ganja_{symptom}_{day}", "Ganja", symptom, count - 10, date))
    conn.executemany("INSERT INTO symptom_reports VALUES(?,?,?,?,?)", symptoms)

    for patient_id in ("patient_hasan", "patient_followup", "patient_104", "patient_207"):
        persist_alerts(conn, patient_id, None, notify, uid, now)
