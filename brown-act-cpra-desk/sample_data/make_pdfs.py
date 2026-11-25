"""Builds one PDF per fictional record in sample_data/records. Needs reportlab (BSD)."""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

here = Path(__file__).parent / "records"
for txt in sorted(here.glob("*.txt")):
    c = canvas.Canvas(str(txt.with_suffix(".pdf")), pagesize=letter)
    c.setTitle(txt.stem)
    c.setFont("Helvetica", 10.5)
    y = 740
    for line in txt.read_text(encoding="utf-8").splitlines():
        c.drawString(64, y, line)
        y -= 15
    c.save()
    print("wrote", txt.with_suffix(".pdf").name)
