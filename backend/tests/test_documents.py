from app.documents import classify, parse_lab


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
