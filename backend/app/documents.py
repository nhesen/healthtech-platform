"""Local-first document storage and deterministic lab parsing for demo data."""
from __future__ import annotations
import hashlib, re
from pathlib import Path
from typing import Any

ALLOWED={"application/pdf","image/png","image/jpeg"}
ALIASES={"hba1c":"HbA1c","hb a1c":"HbA1c","a1c":"HbA1c","glucose":"Glucose","vitamin d":"Vitamin D","hemoglobin":"Hemoglobin","total cholesterol":"Total Cholesterol","cholesterol":"Total Cholesterol","ldl":"LDL","hdl":"HDL","triglycerides":"Triglycerides"}
def file_hash(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def classify(text:str)->tuple[str,float]:
    lower=text.lower()
    if any(x in lower for x in ["hba1c","glucose","hemoglobin","reference range"]):return "LAB_REPORT",.9
    if any(x in lower for x in ["prescription"," rx","dosage"]):return "PRESCRIPTION",.8
    if "discharge" in lower:return "DISCHARGE_SUMMARY",.8
    if any(x in lower for x in ["radiology","x-ray","xray","mri","ultrasound","ct scan"]):return "IMAGING_REPORT",.8
    if any(x in lower for x in ["assessment","consultation","plan"]):return "DOCTOR_REPORT",.7
    return "OTHER",.35
def extract_text(data:bytes,mime:str)->str:
    if mime=="application/pdf":
        try:
            from pypdf import PdfReader
            from io import BytesIO
            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        except Exception:return data.decode("utf-8",errors="ignore")
    return "" # Images retain file and require review/manual entry without OCR.
def parse_lab(text:str)->dict[str,Any]:
    results=[]
    for raw,metric in ALIASES.items():
        pattern=rf"{re.escape(raw)}\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*([%a-zA-Z/]+)?\s*(?:\(?\s*(\d+(?:\.\d+)?)\s*[\-–]\s*(\d+(?:\.\d+)?)\s*\)?)?"
        match=re.search(pattern,text,re.I)
        if match and not any(x["test_name"]==metric for x in results):
            value=float(match.group(1)); unit=match.group(2) or ""; lo,hi=match.group(3),match.group(4)
            results.append({"test_name":metric,"value":value,"unit":unit,"reference_text":f"{lo}-{hi}" if lo and hi else "","reference_min":float(lo) if lo else None,"reference_max":float(hi) if hi else None,"confidence":.9})
    date_match=re.search(r"(?:report\s*date|date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})",text,re.I)
    report_date=date_match.group(1).replace(".","-").replace("/","-") if date_match else None
    source_name=next((line.strip() for line in text.splitlines() if line.strip()),None)
    return {"results":results,"report_date":report_date,"source_name":source_name}
