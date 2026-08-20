"""Generate the text-based lab PDF used in the hackathon demo.

Values match the 10.08.2026 complete blood count used in the seeded comparison.
The bundled PDF is synthetic/sanitized: it does not include identity-document numbers.
"""
from pathlib import Path

lines = [
    "Hasan Nurmammadov - Complete Blood Count",
    "Report date: 2026-08-10",
    "WBC 7.38 10^3/uL 4.5-11",
    "RBC 5.74 10^6/uL 4.5-5.9",
    "Hemoglobin 13.9 g/dL 13.5-17.5",
    "HCT 43.7 % 40-53",
    "MCV 76.2 fL 76-100",
    "MCH 24.2 pg 24-31",
    "MCHC 31.8 g/dL 30-36",
    "RDW-CV 14 % 10-16",
    "PLT 234 10^3/uL 140-400",
    "Iron 92.9 ug/dL 31-168",
    "Ferritin 52.4 ng/mL 21.81-274.66",
]
commands = ["BT", "/F1 12 Tf", "72 750 Td"]
for index, line in enumerate(lines):
    escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    if index:
        commands.append("0 -22 Td")
    commands.append(f"({escaped}) Tj")
commands.append("ET")
stream = "\n".join(commands).encode("ascii")
objects = [
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n",
    f"4 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n",
    b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
]
pdf = bytearray(b"%PDF-1.4\n")
offsets = [0]
for obj in objects:
    offsets.append(len(pdf))
    pdf.extend(obj)
xref = len(pdf)
pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
for offset in offsets[1:]:
    pdf.extend(f"{offset:010d} 00000 n \n".encode())
pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
root = Path(__file__).resolve().parents[1] / "demo_documents"
root.mkdir(exist_ok=True)
(root / "hasan_lab_report.pdf").write_bytes(pdf)
(root / "hasan_lab_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(root / "hasan_lab_report.pdf")
