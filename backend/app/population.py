"""Public-domain NHANES CBC cohort used as the population reference, not as named patients."""
from __future__ import annotations

import csv
import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_PATH = DATA_DIR / "nhanes_cbc_2021_2023.csv.gz"
STATS_PATH = DATA_DIR / "nhanes_cbc_stats.json"

METRIC_COLUMNS = {
    "WBC": "wbc",
    "RBC": "rbc",
    "Hemoglobin": "hemoglobin",
    "HCT": "hct",
    "MCV": "mcv",
    "MCH": "mch",
    "MCHC": "mchc",
    "RDW-CV": "rdw",
    "PLT": "plt",
}

POPULATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS population_cbc (
  seqn INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  sex TEXT,
  age_years INTEGER,
  wbc REAL, rbc REAL, hemoglobin REAL, hct REAL, mcv REAL, mch REAL, mchc REAL, rdw REAL, plt REAL
);
CREATE INDEX IF NOT EXISTS idx_population_cbc_sex_age ON population_cbc(sex, age_years);
"""


def catalog() -> dict[str, Any]:
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8")) if STATS_PATH.exists() else {}
    return {
        "id": "nhanes_cbc_2021_2023",
        "name": "NHANES 2021-2023 Complete Blood Count",
        "license": stats.get("license") or "U.S. public domain (CDC/NCHS)",
        "url": stats.get("url"),
        "source": stats.get("source"),
        "rows": stats.get("all", {}).get("n", 0),
        "male_rows": stats.get("male", {}).get("n", 0),
        "male_12_19_rows": stats.get("male_12_19", {}).get("n", 0),
        "role": "Population reference for percentiles. Not a named clinical record.",
    }


def ensure_population(conn) -> int:
    conn.executescript(POPULATION_SCHEMA)
    count = conn.execute("SELECT COUNT(*) FROM population_cbc").fetchone()[0]
    if count or not CSV_PATH.exists():
        return count
    with gzip.open(CSV_PATH, "rt", encoding="utf-8", newline="") as handle:
        rows = [
            (
                int(float(item["seqn"])), "NHANES_2021_2023", item.get("sex") or None,
                int(float(item["age_years"])) if item.get("age_years") else None,
                float(item["wbc"]), float(item["rbc"]), float(item["hemoglobin"]), float(item["hct"]),
                float(item["mcv"]), float(item["mch"]), float(item["mchc"]), float(item["rdw"]), float(item["plt"]),
            )
            for item in csv.DictReader(handle)
        ]
    conn.executemany(
        "INSERT INTO population_cbc(seqn,source,sex,age_years,wbc,rbc,hemoglobin,hct,mcv,mch,mchc,rdw,plt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _age_years(dob: str | None, today: date | None = None) -> int | None:
    if not dob:
        return None
    try:
        year, month, day = (int(part) for part in dob.split("-"))
    except ValueError:
        return None
    stamp = today or date.today()
    return stamp.year - year - ((stamp.month, stamp.day) < (month, day))


def cohort_for_patient(sex: str | None, dob: str | None) -> tuple[str, str, str | None, int | None, int | None]:
    age = _age_years(dob)
    male = (sex or "").lower().startswith("m")
    if male and age is not None and 12 <= age <= 19:
        return "male_12_19", "M", "M", 12, 19
    if male:
        return "male", "M", "M", None, None
    return "all", "all ages", None, None, None


def percentile_for(conn, metric: str, value: float, sex: str | None = None, age_min: int | None = None, age_max: int | None = None) -> dict[str, Any] | None:
    column = METRIC_COLUMNS.get(metric)
    if column is None or value is None:
        return None
    clauses = [f"{column} IS NOT NULL"]
    params: list[Any] = []
    if sex:
        clauses.append("sex=?")
        params.append(sex)
    if age_min is not None:
        clauses.append("age_years>=?")
        params.append(age_min)
    if age_max is not None:
        clauses.append("age_years<=?")
        params.append(age_max)
    where = " AND ".join(clauses)
    total = conn.execute(f"SELECT COUNT(*) FROM population_cbc WHERE {where}", params).fetchone()[0]
    if not total:
        return None
    below = conn.execute(f"SELECT COUNT(*) FROM population_cbc WHERE {where} AND {column}<=?", (*params, value)).fetchone()[0]
    return {
        "source": "NHANES 2021-2023 CBC",
        "license": "U.S. public domain (CDC/NCHS)",
        "cohort": "male 12-19" if sex == "M" and age_min == 12 else ("male" if sex == "M" else "all ages"),
        "n": total,
        "percentile": round(100 * below / total, 1),
        "disclaimer": "Percentile versus an open population survey, not a diagnosis.",
    }


def attach_population(conn, metrics: list[dict[str, Any]], sex: str | None, dob: str | None) -> list[dict[str, Any]]:
    cohort_id, _label, cohort_sex, age_min, age_max = cohort_for_patient(sex, dob)
    enriched = []
    for item in metrics:
        row = dict(item)
        row["population"] = percentile_for(conn, item["metric"], item.get("to", {}).get("value") if isinstance(item.get("to"), dict) else item.get("current"), cohort_sex, age_min, age_max)
        row["population_cohort"] = cohort_id
        enriched.append(row)
    return enriched
