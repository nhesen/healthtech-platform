import os
from pathlib import Path

os.environ["DATABASE_URL"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app, DB_PATH


def reset():
    if DB_PATH.exists():
        DB_PATH.unlink()
    from app.main import seed
    seed()


PATIENT = {"X-Demo-User": "patient@demo.az"}
ADMIN = {"X-Demo-User": "admin@demo.az"}


def test_nhanes_open_cbc_is_loaded_and_ranks_hasan():
    reset()
    client = TestClient(app)
    population = client.get("/labs/population", headers=PATIENT).json()
    assert population["loaded_rows"] >= 7000
    assert "public domain" in population["license"].lower()
    assert population["male_12_19_rows"] >= 400

    comparison = client.get(
        "/patients/patient_hasan/lab-comparison",
        headers=PATIENT,
        params={"from_date": "2025-09-02", "to_date": "2026-08-10"},
    ).json()
    assert comparison["population"]["rows"] >= 7000
    wbc = next(item for item in comparison["metrics"] if item["metric"] == "WBC")
    mcv = next(item for item in comparison["metrics"] if item["metric"] == "MCV")
    assert wbc["population"]["n"] >= 400
    assert 0 <= wbc["population"]["percentile"] <= 100
    assert mcv["population"]["percentile"] < 25

    overview = client.get("/intelligence/overview", headers=ADMIN).json()
    assert overview["population_cbc_rows"] >= 7000
    assert overview["open_datasets"][0]["id"] == "nhanes_cbc_2021_2023"
