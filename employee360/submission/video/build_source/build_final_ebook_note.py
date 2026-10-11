from pathlib import Path
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader, PdfWriter
root=Path.cwd(); out=root/'walkthrough_final'
styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='NoteBody',fontName='Helvetica',fontSize=10.5,leading=15,spaceAfter=12,textColor=HexColor('#17324B')))
styles['Title'].textColor=HexColor('#102A40')
blocks=[('Final validation note','title'),('Anthony Grant Apollis | 11 October 2026','body'),('Read this note with the historical Databricks evidence','heading'),('The original eBook pages describe earlier cloud runs. Their figures and screenshots are retained as historical evidence. They do not certify that the later local Python, SQL, PySpark and dbt files are identical implementations. Original printed page references still refer to the original body of the eBook.','body'),('Corrected local validation','heading'),('The local Python checker now correctly accepts HR Terminated with payroll Stopped. Its earlier mapping incorrectly flagged E1012 and E1041. After correction, the supplied data produces 17 rule findings across 12 employee IDs; all 10 local controls find a defect and release remains BLOCK. The new regression test accepts valid status pairs and detects a contradictory Payable status.','body'),('Why the counts differ','heading'),('A finding row, an affected employee and a lifecycle issue are different units. The historical dashboard starts with 17 lifecycle issues and shows 8 resolved, 2 new and 11 open after the simulated third delivery. Its 19 issue-history rows and 13 affected employees are historical figures. The corrected local checker uses DQ01-DQ07 and RC01-RC03, while the dashboard uses DQ01-DQ06 and RC01-RC04. Equal totals do not establish rule-by-rule parity.','body'),('Coverage and remaining implementation limits','heading'),('The local checker has narrower profile-field reconciliation than the dashboard, a fixed freshness cutoff, and a supplied-data-specific E1042 exception. These are documented limitations, not production-ready generic policies. No fresh Databricks or Azure DevOps deployment is claimed. Consult VALIDATION_SCOPE.md and the machine-readable outputs before interpreting or deploying any component.','body'),('Walkthrough and reproducibility','heading'),('The accompanying full video uses the corrected slides, historical dashboard captures and a disclosed computer-generated narrator. It is a slide walkthrough, not a live screen recording or a voice clone. START_HERE.md explains the review order. PACKAGE_VALIDATION.json records the fresh-extraction tests, and MANIFEST.sha256 covers the packaged files.','body')]
buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=46,leftMargin=46,topMargin=40,bottomMargin=40)
flow=[]
for text,kind in blocks:
    flow.append(Paragraph(text,styles['Title'] if kind=='title' else styles['Heading3'] if kind=='heading' else styles['NoteBody']))
doc.build(flow)
note=PdfReader(io.BytesIO(buf.getvalue())); assert len(note.pages)==1,len(note.pages)
source=root/'kimball_assignment_update/Employee360_DQ_Submission/ebook/Employee360_DQ_Submission_Final.pdf'
original=PdfReader(source); writer=PdfWriter()
writer.add_page(original.pages[0]); writer.add_page(note.pages[0])
for page in original.pages[1:]: writer.add_page(page)
writer.add_metadata({'/Title':'Employee 360 Data Quality - final validated package','/Author':'Anthony Grant Apollis'})
final=out/'Employee360_DQ_Submission_Final.pdf'
with final.open('wb') as f: writer.write(f)
assert len(PdfReader(final).pages)==len(original.pages)+1
(out/'validation_note.pdf').write_bytes(buf.getvalue())
print(final, 'pages',len(writer.pages))
