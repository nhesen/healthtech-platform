"""Generate the synthetic, text-based lab PDF used in the hackathon demo."""
from pathlib import Path

lines=["Hasan M. - Synthetic Lab Report","Report date: 2026-08-18","HbA1c 6.3 % 4.0-5.6","Glucose 108 mg/dL 70-99","Vitamin D 28 ng/mL 30-100","Hemoglobin 14.1 g/dL 12-16"]
commands=["BT","/F1 16 Tf","72 750 Td"]
for index,line in enumerate(lines):
    escaped=line.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    if index: commands.append("0 -28 Td")
    commands.append(f"({escaped}) Tj")
commands.append("ET")
stream="\n".join(commands).encode("ascii")
objects=[b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n",f"4 0 obj << /Length {len(stream)} >> stream\n".encode()+stream+b"\nendstream endobj\n",b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"]
pdf=bytearray(b"%PDF-1.4\n"); offsets=[0]
for obj in objects: offsets.append(len(pdf)); pdf.extend(obj)
xref=len(pdf); pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
target=Path(__file__).resolve().parents[1]/"demo_documents"/"hasan_lab_report.pdf"
target.parent.mkdir(exist_ok=True); target.write_bytes(pdf); print(target)
