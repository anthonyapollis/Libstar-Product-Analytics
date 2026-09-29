# Rebuilding the submission document

`JSB_Candidate_Submission.docx` is generated, not hand-edited, so it always reflects the
committed evidence (screenshots, figures).

```bash
npm install docx          # docx-js
python build_pdf.py       # writes ../JSB_Candidate_Submission.docx and .pdf
```

`build_pdf.py` renders twice. The first render finds the page each numbered heading lands on
(`headings.json` → `pages.json`); the second puts those page numbers into the contents page and the
requirements index. It checks that the numbers are stable.

```bash
# the manual equivalent, without page numbers:
node main.js && soffice --headless --convert-to pdf ../JSB_Candidate_Submission.docx
```

- `build.js`: page furniture and helpers (title page, headings, tables, images).
- `main.js`: the content of each section, plus the front matter: contents, how to read, results at a
  glance, and the requirements index that maps every line of the brief to a section and page.
- `build_pdf.py`: the two-pass build that fills in the page numbers.
- `make_screenshot.py`: renders captured terminal output as the terminal-style screenshots under
  each exercise's `screenshots/` folder.
