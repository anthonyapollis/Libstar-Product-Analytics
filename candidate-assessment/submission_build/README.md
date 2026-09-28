# Rebuilding the submission document

`JSB_Candidate_Submission.docx` is generated, not hand-edited, so it always reflects the
committed evidence (screenshots, figures).

```bash
npm install docx          # docx-js
node main.js              # writes ../JSB_Candidate_Submission.docx
soffice --headless --convert-to pdf ../JSB_Candidate_Submission.docx
```

- `build.js`: page furniture and helpers (title page, headings, tables, images).
- `main.js`: the content of each section.
- `make_screenshot.py`: renders captured terminal output as the terminal-style screenshots under
  each exercise's `screenshots/` folder.
