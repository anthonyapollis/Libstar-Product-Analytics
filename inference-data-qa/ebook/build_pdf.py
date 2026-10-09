"""Build Employee360_DQ_eBook.docx and .pdf with real page numbers in the contents and requirements index.

Pass 1 renders with placeholder pages; each heading is then found in the PDF and its page saved to pages.json;
pass 2 renders again with those numbers (a third pass only if anything moved).
Needs: node with the `docx` package (NODE_PATH may point at it), LibreOffice (soffice), pdftotext, pdfinfo.
Usage: python ebook/build_pdf.py
"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCX, PDF = ROOT / "Employee360_DQ_eBook.docx", ROOT / "Employee360_DQ_eBook.pdf"


def render():
    subprocess.run(["node", str(HERE / "build_ebook.js")], check=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(ROOT), str(DOCX)],
                   check=True, capture_output=True)


def norm(t):
    return re.sub(r"\s+", " ", t.replace("—", "-").replace("–", "-")).strip()


def locate():
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout).group(1))
    pages = [norm(subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(PDF), "-"], capture_output=True, text=True).stdout)
             for i in range(1, n + 1)]
    found = {}
    for h in json.loads((HERE / "headings.json").read_text()):
        hits = [i + 1 for i, t in enumerate(pages) if norm(h["label"]) in t]
        if not hits:
            raise SystemExit(f"heading not found in PDF: {h['label']}")
        found[h["num"]] = hits[-1]  # the last hit is the heading itself; earlier ones are the contents page
    return found, n


(HERE / "pages.json").unlink(missing_ok=True)
render()
first, _ = locate()
(HERE / "pages.json").write_text(json.dumps(first, indent=1))
render()
second, n = locate()
if second != first:
    (HERE / "pages.json").write_text(json.dumps(second, indent=1))
    render()
    third, n = locate()
    assert third == second, "page numbers did not settle"
print(f"{n} pages; {len(second)} headings located")
