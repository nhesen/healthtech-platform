# Open datasets bundled with HealthTech

## NHANES 2021–2023 Complete Blood Count

- Files: `nhanes_cbc_2021_2023.csv.gz`, `nhanes_cbc_stats.json`
- Source: CDC / NCHS National Health and Nutrition Examination Survey, August 2021–August 2023
- Laboratory file: `CBC_L` — https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/CBC_L.htm
- Demographics file: `DEMO_L` (sex and age only) — used to age-match Hasan's comparison
- License: U.S. government public domain
- Rows kept: complete CBC panels with WBC, RBC, hemoglobin, HCT, MCV, MCH, MCHC, RDW, and platelets

This is a de-identified population survey, not a named clinical record. Hasan's two local reports remain the case-level timeline; NHANES is the reference cohort used for percentiles.

Regenerate from CDC (requires pandas):

```text
python backend/scripts/import_nhanes_cbc.py
```

## Reviewed but not bundled

| Dataset | Size | Why it was not copied into the repo |
|---|---|---|
| Klinikum Lippe CBC (Zenodo 15674541) | 523,844 samples / 77,355 patients | Real hospital extracts, 46 MB, no clear Creative Commons license on the record |
| Sri Lanka FBC (Zenodo 18666957) | 222,042 records | Real hospital extracts; too large to vendor and not needed for the live demo path |
| MIMIC-IV | credentialed PhysioNet | Not open without CITI training; cannot be redistributed here |
| Synthea | Apache 2.0 synthetic generator | Useful to grow a FHIR corpus later; NHANES already supplies a legal CBC panel |

Hasan's 02.09.2025 and 10.08.2026 reports stay the patient-identifiable demo case. Population percentiles never copy his identity into the open cohort.
