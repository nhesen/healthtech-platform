"""Additional tables for healthcare intelligence. Applied idempotently by migrate()."""

INTELLIGENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS medications (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active_ingredient TEXT NOT NULL,
  drug_class TEXT NOT NULL,
  penicillin_class INTEGER NOT NULL DEFAULT 0 CHECK(penicillin_class IN (0,1)),
  high_dose_mg REAL
);
CREATE TABLE IF NOT EXISTS prescriptions (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  doctor_id TEXT NOT NULL,
  medication_id TEXT NOT NULL,
  dosage TEXT NOT NULL,
  dose_mg REAL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','STOPPED')),
  started_at TEXT NOT NULL,
  notes TEXT DEFAULT '',
  FOREIGN KEY(patient_id) REFERENCES patients(id),
  FOREIGN KEY(doctor_id) REFERENCES doctors(id),
  FOREIGN KEY(medication_id) REFERENCES medications(id)
);
CREATE TABLE IF NOT EXISTS medication_interactions (
  id TEXT PRIMARY KEY,
  medication_a TEXT NOT NULL,
  medication_b TEXT NOT NULL,
  interaction_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  explanation TEXT NOT NULL,
  recommended_action TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medication_alerts (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  medication_a TEXT,
  medication_b TEXT,
  doctor_a TEXT,
  doctor_b TEXT,
  explanation TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('NEW','REVIEWED','RESOLVED','DISMISSED')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emergency_access (
  id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  device TEXT,
  started_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS hospital_ops (
  hospital_id TEXT PRIMARY KEY,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  er_load_percent INTEGER NOT NULL CHECK(er_load_percent>=0 AND er_load_percent<=100),
  icu_total INTEGER NOT NULL,
  icu_available INTEGER NOT NULL,
  available_beds INTEGER NOT NULL,
  ambulances INTEGER NOT NULL,
  avg_wait_minutes INTEGER NOT NULL,
  specialties TEXT NOT NULL,
  equipment TEXT NOT NULL,
  FOREIGN KEY(hospital_id) REFERENCES hospitals(id)
);
CREATE TABLE IF NOT EXISTS blood_inventory (
  id TEXT PRIMARY KEY,
  hospital_id TEXT NOT NULL,
  blood_type TEXT NOT NULL,
  units INTEGER NOT NULL CHECK(units>=0),
  updated_at TEXT NOT NULL,
  FOREIGN KEY(hospital_id) REFERENCES hospitals(id)
);
CREATE TABLE IF NOT EXISTS resource_requests (
  id TEXT PRIMARY KEY,
  hospital_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  blood_type TEXT,
  units_needed INTEGER NOT NULL CHECK(units_needed>=1),
  priority TEXT NOT NULL CHECK(priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  status TEXT NOT NULL CHECK(status IN ('OPEN','MATCHED','FULFILLED','CANCELLED')),
  created_at TEXT NOT NULL,
  FOREIGN KEY(hospital_id) REFERENCES hospitals(id)
);
CREATE TABLE IF NOT EXISTS resource_matches (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  source_hospital_id TEXT NOT NULL,
  units INTEGER NOT NULL,
  distance_km REAL NOT NULL,
  travel_minutes INTEGER NOT NULL,
  priority TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(request_id) REFERENCES resource_requests(id)
);
CREATE TABLE IF NOT EXISTS symptom_reports (
  id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  symptom TEXT NOT NULL,
  count INTEGER NOT NULL CHECK(count>=0),
  report_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS epidemic_signals (
  id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  signal TEXT NOT NULL,
  change_percent REAL NOT NULL,
  confidence REAL NOT NULL,
  risk TEXT NOT NULL CHECK(risk IN ('LOW','MEDIUM','HIGH')),
  recommendation TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id,status);
CREATE INDEX IF NOT EXISTS idx_med_alerts_patient ON medication_alerts(patient_id,status);
CREATE INDEX IF NOT EXISTS idx_break_glass_actor ON emergency_access(actor_id,patient_id,expires_at);
CREATE INDEX IF NOT EXISTS idx_symptoms_region_date ON symptom_reports(region,report_date);
"""
