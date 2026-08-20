from app.documents import classify, parse_lab

ABSHERON_2025 = """
TEST ADI * NƏTİCƏ VAHİD REFERANS
Qeydiyyat Tar. : 02.09.2025 09:25:09 Şöbə : Revmatologiya
WBC - Leykositlər 10.64 10^3/μL 3,84 - 9,84
RBC - Eritrosit 5.95 10^6/μL 4,03 - 5,29
HGB - Hemoqlobin 14.3 g/dL 11,0 - 14,5
HCT - Hematokrit 44.8 % 33,9 - 43,5
MCV - Eritrositlərin orta həcmi 75.3 fL 76,7 - 90,0
MCH - Eritrositdə hemoqlobinin orta miqdarı 24 pg 25,2 - 30,2
MCHC - Eritrositdə hemoqlobinin orta konsentrasiyası 31.9 g/dL 31,8 - 34,8
RDW-CV - Eritrositlərin paylanma enliliyinin % miqdarı 15.1 % 12,3 - 14,6
PLT - Trombositlər 341 10^3/μL 175 - 332
Mentzer indeksi 12.66
"""

HEMOGRAM_2026 = """
Nümunənin Alınma Tarixi : 10.08.2026 11:18:58
Xidmət Nəticə Referans Aralığı Ölçü vahidi
4.5 - 11	WBC (Leykositlər) 7.38 K/mm3
4.5 - 5.9	RBC (Eritrositlər) 5.74 M/mm3
13.5 - 17.5	HGB (Hemoglobin) 13.9 g/dL
40 - 53	HCT (Hematokrit) 43.7 %
76 - 100	MCV (Eritrositlərin orta həcmi) 76.2 fL
24 - 31	MCH (Er-də HGB orta həcmi) 24.2 pg
30 - 36	MCHC (Er-də HGB orta kons.) 31.8 g/dL
10 - 16	RDW_CV (Erit-lərin pay.geniş. ) 14 %
140 - 400	PLT (Trombositlər) 234 K/mm3
31 - 168	Dəmir, Fe 92.9 ug/dL
21.81 - 274.66	Ferritin 52.4 ng/mL
"""


def test_demo_lab_report_is_classified_and_parsed():
    text = "HbA1c 6.3 % 4.0-5.6\nGlucose 108 mg/dL 70-99\nVitamin D 28 ng/mL 30-100"
    assert classify(text)[0] == "LAB_REPORT"
    values = {item["test_name"]: item["value"] for item in parse_lab(text)["results"]}
    assert values == {"HbA1c": 6.3, "Glucose": 108.0, "Vitamin D": 28.0}

def test_extended_classification_and_normalization():
    parsed=parse_lab("Synthetic Lab\nReport date: 2026-08-19\nLDL 120 mg/dL 0-99\nHDL 48 mg/dL 40-60\nTriglycerides 140 mg/dL 0-150")
    assert {x["test_name"] for x in parsed["results"]}=={"LDL","HDL","Triglycerides"}
    assert parsed["report_date"]=="2026-08-19" and parsed["source_name"]=="Synthetic Lab"
    assert classify("MRI radiology report")[0]=="IMAGING_REPORT"

def test_absheron_2025_cbc_is_parsed():
    assert classify(ABSHERON_2025)[0] == "LAB_REPORT"
    parsed = parse_lab(ABSHERON_2025)
    values = {item["test_name"]: item["value"] for item in parsed["results"]}
    assert parsed["report_date"] == "2025-09-02"
    assert values["WBC"] == 10.64
    assert values["RBC"] == 5.95
    assert values["Hemoglobin"] == 14.3
    assert values["HCT"] == 44.8
    assert values["MCV"] == 75.3
    assert values["PLT"] == 341
    assert values["Mentzer"] == 12.66

def test_2026_hemogram_is_parsed_with_leading_reference_ranges():
    parsed = parse_lab(HEMOGRAM_2026)
    values = {item["test_name"]: item["value"] for item in parsed["results"]}
    assert parsed["report_date"] == "2026-08-10"
    assert values["WBC"] == 7.38
    assert values["Hemoglobin"] == 13.9
    assert values["PLT"] == 234
    assert values["Iron"] == 92.9
    assert values["Ferritin"] == 52.4
    assert values["RDW-CV"] == 14
