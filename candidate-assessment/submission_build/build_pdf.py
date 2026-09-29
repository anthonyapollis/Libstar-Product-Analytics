"""Build JSB_Candidate_Submission.docx and .pdf with real page numbers in the contents and the
requirements index.

Pass 1 renders the document with placeholder page numbers; the PDF is then searched for each numbered
heading (headings.json, written by main.js) and the pages go into pages.json; pass 2 renders again with
those numbers. The front matter's length doesn't depend on the numbers, so one extra pass settles it,
and the script checks that the pages didn't move.
Needs: node with the `docx` package, LibreOffice (soffice) and pdftotext.
Usage (from this folder): python build_pdf.py
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent  # candidate-assessment/
DOCX, PDF = OUT / "JSB_Candidate_Submission.docx", OUT / "JSB_Candidate_Submission.pdf"


def render():
    subprocess.run(["node", "main.js"], cwd=HERE, check=True, capture_output=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(OUT), str(DOCX)],
                   check=True, capture_output=True)


def norm(t):
    return re.sub(r"\s+", " ", t.replace("—", "-").replace("–", "-")).strip()


def locate():
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout).group(1))
    pages = [norm(subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(PDF), "-"],
                                 capture_output=True, text=True).stdout) for i in range(1, n + 1)]
    found = {}
    for h in json.loads((HERE / "headings.json").read_text()):
        label = norm(h["label"])
        hits = [i + 1 for i, t in enumerate(pages) if label in t]
        if not hits:
            raise SystemExit(f"heading not found in PDF: {h['label']}")
        found[h["num"]] = hits[-1]        # the last hit is the chapter itself; earlier hits are the contents page
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
    second = third
print(f"{n} pages; {len(second)} headings located; contents and requirements index carry real page numbers")
