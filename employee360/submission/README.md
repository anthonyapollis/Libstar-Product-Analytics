# Employee 360 Data Quality - runnable materials
Begin with START_HERE.md and the validation note after the eBook cover.

## Local setup and checks
From this extracted folder, using Python 3.11 or a compatible version:

    python -m pip install -r requirements.txt
    python src/employee360_pipeline.py --input data --output outputs/run_local
    python tests/test_pipeline.py
    python tests/test_incremental.py

Expected supplied-data result: 10 rules, 10 failing rules, 17 finding rows and BLOCK. Both tests should print PASS. The status regression explicitly accepts Terminated/Stopped and detects Terminated/Payable.

## Files
- src/employee360_pipeline.py: local pandas profiling, controls, reconciliation and monitoring.
- src/incremental_loader.py: file-hash change and skip logic.
- sql/: profiling, reconciliation and monitoring SQL.
- notebooks/: Databricks PySpark source.
- dbt_employee360/: optional SQL models, documentation and tests.
- azure-pipelines.yml: CI configuration; not proof of a live Azure DevOps deployment.
- outputs/supplied_data/: corrected local reference results.
- evidence/: historical dashboard captures and diagrams.
- ebook/: written submission, model and validation note.
- presentation/: corrected deck and full narration.
- video/: full walkthrough, captions and technical validation.

Read VALIDATION_SCOPE.md before deploying. Local and historical cloud implementations are not equivalent in all rules. The local implementation has a fixed assessment date, a supplied-data-specific E1042 exception, and narrower profile-field coverage. Do not treat it as a generic production policy engine.
