# Walkthrough video script (about 8 minutes)

Show the working solution, not slides. Have open: the Databricks notebook run (or a terminal for `run_local.py`),
`outputs/monitoring.csv` and `docs/findings.md`.

**0:00–1:00 Profile and the biggest risk**
- Show the profile counts: all three files have 48 rows, yet payroll has 47 distinct IDs and Employee 360 has 47
  IDs that exist in HR.
- *"Matching counts are the first trap. The highest risk is twofold: Employee 360 lists the wrong people,
  and a leaver, E1029, is still payable in payroll."*

**1:00–5:00 Checks, failures and reconciliation**
- **The six checks** in `02_checks.sql`:
  - DQ01 uses a window count;
  - DQ02 uses a self-join so top managers may have a blank manager;
  - DQ03 is an anti-join;
  - DQ04 is the HR-to-payroll status rule;
  - DQ05 is validity;
  - DQ06 is freshness.

  Point out that each returns employee IDs.
- **The reconciliation:**
  - E1027 is missing and E1099 is unexpected;
  - the R2 counts;
  - **R3: net R64,600 against gross R225,200.**
- **The PySpark `reconcile_fields`:**
  - field ownership (HR against payroll);
  - CPT is not flagged;
  - E1042 is a legitimate future-dated exception;
  - E1015 is "Cannot verify".
- **The monitoring table:** severity, action, alert threshold, and `blocks_release` leading to **BLOCK**.

**5:00–6:30 Root cause**
- Show `recon_lookalike.csv`: E1099 equals E1028 on 8 of 8 attributes.
- **Facts against hypothesis:**
  - fact: E1099 was written by the 10-08 build;
  - hypothesis: a crosswalk or identity-resolution step.
- **What would confirm it:** the crosswalk entries, Delta history and the job logs.
- **Owner:** the Employee 360 build team with the MDM steward.

**6:30–8:00 Operating it**
- `run_incremental_local.py` output, three runs:
  1. full load, 17 issues;
  2. same files: **skipped, nothing read**;
  3. fixes: **8 resolved, 2 new alerts only**.
- `databricks.yml`: the checks task gates the publish task.
- `azure-pipelines.yml`: PR tests run on local PySpark at no Databricks cost.
- **What I would not run every time:** the full profile and the look-alike self-join, which run weekly.

**8:00–9:00 AI use and next steps**
- **Tools:** Claude Code built it, Codex reviewed it.
- **One correction:** the `F.first()` silent pass on E1015, caught by the independent check.
- **Your own challenge** (see `docs/ai_use.md`).
- **Next:**
  - get the crosswalk and Delta history to prove the root cause;
  - agree the leaver rule with payroll;
  - add the changed-keys filter to the row-level checks for scale.
