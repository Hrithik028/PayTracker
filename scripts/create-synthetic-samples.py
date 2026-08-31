"""Generate fictional, non-personal test documents for local OCR experiments."""
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
SAMPLES.mkdir(exist_ok=True)

lines = [
    "SYNTHETIC SAMPLE - NOT A REAL PAYSLIP",
    "Employer: Example Retail Pty Ltd",
    "Employee: Sample Person",
    "Pay Period: 01/07/2026 to 14/07/2026",
    "Payment Date: 16/07/2026",
    "Ordinary 20.00 30.0000 600.00",
    "Gross Pay: $600.00",
    "Tax Withheld: $100.00",
    "Superannuation: $72.00",
    "Net Pay: $500.00",
    "Total Paid Hours: 20.00",
]

pdf = fitz.open()
page = pdf.new_page(width=595, height=842)
page.insert_text((55, 70), "\n".join(lines), fontsize=12, lineheight=1.5)
pdf.save(SAMPLES / "synthetic-payslip.pdf")
pdf.close()

image = Image.new("RGB", (1000, 680), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.load_default(size=28)
shift_lines = [
    "SYNTHETIC SAMPLE - SHIFT SCREENSHOT",
    "Wed 01/07/2026 9:00am - 5:30pm Break 30 min",
    "Thu 02/07/2026 10:00pm - 6:30am Break 30 min",
    "Sat 04/07/2026 8:00am - 1:00pm Break 0 min",
]
for index, line in enumerate(shift_lines):
    draw.text((45, 60 + index * 105), line, fill="#0f2747", font=font)
image.save(SAMPLES / "synthetic-timing-screenshot.png")
print(f"Created synthetic samples in {SAMPLES}")

