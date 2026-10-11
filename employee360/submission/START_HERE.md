# Employee 360 Data Quality
Anthony Grant Apollis | Final reader guide

Extract this ZIP once into a new empty folder. Open the files from that folder.

## Review order
1. Open **ebook/Employee360_DQ_Submission_Final.pdf**. Read the final validation note immediately after the cover, then the executive summary and requirements index. The appendices include the data model, join map, Kimball principles and dbt discussion.
2. Play **video/Employee360_DQ_Full_Walkthrough.mp4**: approximately 9 minutes, with narration and burned-in captions. The male voice is computer-generated, not a clone of Anthony. The video walks through the actual slides and historical evidence; it is not a live screen recording.
3. Open **presentation/Employee360_DQ_Walkthrough_Anthony_Apollis.pptx** if you want to inspect the slides. The full narration is in presentation/NARRATION_NOTES.md.
4. Inspect **evidence/browser_screenshots/** and **outputs/supplied_data/**. Historic Databricks and corrected local results have different scopes; read VALIDATION_SCOPE.md.
5. Review **src/**, **sql/**, **notebooks/**, **dbt_employee360/**, **tests/** and **azure-pipelines.yml**. Follow README.md to run the local checks.

## Result interpretation
- Corrected local result: **17 rule findings across 12 employees**, 10 controls finding defects, release **BLOCK**.
- The previous local count of 19 included two false positives: valid HR Terminated / payroll Stopped pairs. This is fixed and regression-tested.
- The historical dashboard has its own rule and issue model. Its Run 1 has 17 open lifecycle issues. Simulated Run 3 resolves 8, introduces 2 and leaves 11 open. This does not claim the supplied files were repaired.
- E1042 is a documented legitimate exception, excluded from failure counters.
- A technically successful run can correctly fail quality controls. A technical job failure requires an engineering repair.

## Reproduce
Use the commands in README.md. PACKAGE_VALIDATION.json records tests from a fresh extraction. MANIFEST.sha256 lists each included file's checksum.

## Private dashboard
https://dbc-ea48b979-9753.cloud.databricks.com/dashboardsv3/01f1c4297bf619938e952fea8dfa289b/published
This requires existing workspace access. The screenshots are available offline. Credentials are not included.

The full video now satisfies the requested duration. It remains a narrated slide explanation, so it should not be described as a live demonstration of code execution.
