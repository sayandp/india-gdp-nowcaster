"""Render reports/report.md to reports/report.pdf with a headless Chromium browser (Edge or Chrome).

Usage: python tools/export_report_pdf.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mistune

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "reports" / "report.md", ROOT / "reports" / "report.pdf"

CSS = """
@page { size: A4; margin: 13mm 14mm; }
body { font-family: "Segoe UI", Helvetica, Arial, sans-serif; font-size: 8.6pt; line-height: 1.3; color: #1F2933; }
h1 { font-size: 14pt; margin: 0 0 2px; }
h2 { font-size: 10.5pt; margin: 9px 0 3px; border-bottom: 1px solid #E4E7EB; padding-bottom: 1px; }
p, ul { margin: 3px 0; }
ul { padding-left: 16px; }
li { margin: 1px 0; }
table { border-collapse: collapse; margin: 4px 0; font-size: 8.2pt; }
th, td { border-bottom: 1px solid #E4E7EB; padding: 2px 7px; text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { background: #F5F7FA; }
code { font-size: 8pt; }
"""

def browser():
    candidates = [os.environ.get("BROWSER"), shutil.which("msedge"), shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for c in candidates:
        if c and Path(c).exists():
            return c
    sys.exit("No Edge or Chrome found. Set BROWSER to a Chromium-based browser executable.")

html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{mistune.html(SRC.read_text(encoding='utf8'))}</body></html>"
with tempfile.TemporaryDirectory() as tmp:
    page = Path(tmp) / "report.html"
    page.write_text(html, encoding="utf8")
    subprocess.run([browser(), "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={tmp}",
                    f"--print-to-pdf={OUT}", page.as_uri()], check=True, capture_output=True, timeout=120)
print("Wrote", OUT)
