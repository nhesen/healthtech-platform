"""Local-first document storage and deterministic lab parsing for demo data."""
from __future__ import annotations
import hashlib, re
from typing import Any

ALLOWED={"application/pdf","image/png","image/jpeg"}
# Longer keys are matched first so MCHC wins over MCH and Hemoqlobin wins over HGB.
ALIASES={
    "hba1c":"HbA1c","hb a1c":"HbA1c","a1c":"HbA1c",
    "vitamin d":"Vitamin D","total cholesterol":"Total Cholesterol","cholesterol":"Total Cholesterol",
    "triglycerides":"Triglycerides","glucose":"Glucose","ldl":"LDL","hdl":"HDL",
    "hemoqlobin":"Hemoglobin","hemoglobin":"Hemoglobin","hematokrit":"HCT",
    "trombositlər":"PLT","trombositler":"PLT","ferritin":"Ferritin","mentzer":"Mentzer",
    "dəmir, fe":"Iron","demir, fe":"Iron","iron":"Iron","rdw-cv":"RDW-CV","rdw_cv":"RDW-CV","rdw-sd":"RDW-SD",
    "mchc":"MCHC","wbc":"WBC","rbc":"RBC","hgb":"Hemoglobin","hct":"HCT",
    "mcv":"MCV","mch":"MCH","plt":"PLT","esr":"ESR","eçs":"ESR",
}
_DATE_LABEL=re.compile(r"(?:nümunənin alınma(?:\s*tarixi)?|qeydiyyat\s*tar\.?|report\s*date|nüm\.?\s*qəbul)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})",re.I)
_ANY_DATE=re.compile(r"(?:report\s*date|date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})",re.I)

def file_hash(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def classify(text:str)->tuple[str,float]:
    lower=text.lower()
    if any(x in lower for x in ["hba1c","glucose","hemoglobin","hemoqlobin","hemogram","wbc","leykosit","referans","reference range"]):return "LAB_REPORT",.9
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
def _number(raw:str)->float:return float(raw.replace(",","."))
def _normalize_date(raw:str)->str:
    raw=raw.replace("/",".").replace("-",".") if raw.count("-")==2 and not re.match(r"\d{4}-",raw) else raw
    if re.match(r"\d{4}-\d{2}-\d{2}$",raw):return raw
    parts=re.split(r"[./-]",raw)
    if len(parts)!=3:return raw.replace(".","-").replace("/","-")
    a,b,c=parts
    if len(c)==4:
        day,month=int(a),int(b)
        if day>12 or "." in raw:return f"{c}-{month:02d}-{day:02d}"
        return f"{c}-{int(a):02d}-{int(b):02d}"
    if len(a)==4:return f"{a}-{int(b):02d}-{int(c):02d}"
    return raw
def parse_lab(text:str)->dict[str,Any]:
    results=[]
    for raw,metric in sorted(ALIASES.items(),key=lambda item:len(item[0]),reverse=True):
        pattern=rf"(?:(?P<lo>\d+(?:[.,]\d+)?)\s*[\-–]\s*(?P<hi>\d+(?:[.,]\d+)?)\s*)?{re.escape(raw)}\b[^\d]{{0,80}}(?P<value>\d+(?:[.,]\d+)?)"
        match=re.search(pattern,text,re.I)
        if not match or any(x["test_name"]==metric for x in results):continue
        value=_number(match.group("value"))
        trailing=text[match.end():match.end()+48]
        unit_match=re.match(r"\s*([%A-Za-zμµ^/0-9-]+)",trailing)
        unit=(unit_match.group(1) if unit_match else "") or ""
        lo,hi=match.group("lo"),match.group("hi")
        if not (lo and hi):
            after=re.search(r"(\d+(?:[.,]\d+)?)\s*[\-–]\s*(\d+(?:[.,]\d+)?)",trailing)
            if after:lo,hi=after.group(1),after.group(2)
        results.append({"test_name":metric,"value":value,"unit":unit,"reference_text":f"{lo}-{hi}" if lo and hi else "","reference_min":_number(lo) if lo else None,"reference_max":_number(hi) if hi else None,"confidence":.9})
    date_match=_DATE_LABEL.search(text) or _ANY_DATE.search(text)
    report_date=_normalize_date(date_match.group(1)) if date_match else None
    source_name=next((line.strip() for line in text.splitlines() if line.strip()),None)
    return {"results":results,"report_date":report_date,"source_name":source_name}
