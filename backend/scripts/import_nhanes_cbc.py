"""Download CDC NHANES CBC + demographics and write the bundled public-domain cohort.

Requires pandas. Runtime seed does not use pandas; it reads the gzip CSV with stdlib.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data"
CBC_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/CBC_L.xpt"
DEMO_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DEMO_L.xpt"
METRICS = ("wbc", "rbc", "hemoglobin", "hct", "mcv", "mch", "mchc", "rdw", "plt")


def _rename(frame, mapping: dict[str, str]):
    frame.columns = [c.decode() if isinstance(c, bytes) else c for c in frame.columns]
    return frame[list(mapping)].rename(columns=mapping)


def _block(frame):
    out = {"n": int(len(frame))}
    for col in METRICS:
        series = frame[col].astype(float)
        out[col] = {
            "n": int(series.count()),
            "mean": round(float(series.mean()), 3),
            "p5": round(float(series.quantile(0.05)), 3),
            "p25": round(float(series.quantile(0.25)), 3),
            "p50": round(float(series.quantile(0.50)), 3),
            "p75": round(float(series.quantile(0.75)), 3),
            "p95": round(float(series.quantile(0.95)), 3),
        }
    return out


def main() -> None:
    import pandas as pd

    ROOT.mkdir(exist_ok=True)
    cbc_path, demo_path = ROOT / "CBC_L.xpt", ROOT / "DEMO_L.xpt"
    urllib.request.urlretrieve(CBC_URL, cbc_path)
    urllib.request.urlretrieve(DEMO_URL, demo_path)
    cbc = _rename(pd.read_sas(cbc_path, format="xport"), {
        "SEQN": "seqn", "LBXWBCSI": "wbc", "LBXRBCSI": "rbc", "LBXHGB": "hemoglobin", "LBXHCT": "hct",
        "LBXMCVSI": "mcv", "LBXMCHSI": "mch", "LBXMC": "mchc", "LBXRDW": "rdw", "LBXPLTSI": "plt",
    })
    demo = _rename(pd.read_sas(demo_path, format="xport"), {"SEQN": "seqn", "RIAGENDR": "sex_code", "RIDAGEYR": "age_years"})
    frame = cbc.merge(demo, on="seqn", how="inner").dropna(subset=list(METRICS))
    frame["sex"] = frame["sex_code"].map({1: "M", 2: "F"})
    frame["seqn"] = frame["seqn"].astype(int)
    frame["age_years"] = frame["age_years"].astype(int)
    for col in METRICS:
        frame[col] = frame[col].astype(float).round(3)
    frame = frame[["seqn", "sex", "age_years", *METRICS]].dropna()
    frame.to_csv(ROOT / "nhanes_cbc_2021_2023.csv.gz", index=False, compression="gzip")
    stats = {
        "source": "NHANES August 2021-August 2023 Complete Blood Count (CBC_L) joined to DEMO_L",
        "license": "U.S. public domain (CDC/NCHS)",
        "url": "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Laboratory&Cycle=2021-2023",
        "all": _block(frame),
        "male": _block(frame[frame.sex == "M"]),
        "male_12_19": _block(frame[(frame.sex == "M") & (frame.age_years >= 12) & (frame.age_years <= 19)]),
    }
    (ROOT / "nhanes_cbc_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    cbc_path.unlink(missing_ok=True)
    demo_path.unlink(missing_ok=True)
    print(f"rows={len(frame)} csv={ROOT / 'nhanes_cbc_2021_2023.csv.gz'}")


if __name__ == "__main__":
    main()
