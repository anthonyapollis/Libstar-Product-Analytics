# Local setup package: provenance (QA-08)

| Item | Value |
|---|---|
| Package | `JSB_Local_Setup_v5.zip` (113 entries, 93 files) |
| SHA-256 | `4e900b9c29f9c03b6a963967c6435cbf31d64d83e426f04b80a98ab53ed07356` |
| Source commit | `2057296f0e6b1511bc9d8a1c09b3bc0fad940dfc` (branch `claude/sleepy-hawking-uiq0u9`) |
| Contents | `candidate-assessment/` paths `local_load`, `TABLE_INVENTORY.md`, `exercise2-ingestion`, `exercise3-schema-design`, `dbt_jsb_assessment`, as committed (no build output, no virtualenv) |
| Built with | `git archive`, git 2.43.0 |
| Per-file hashes | [`local_setup_v5_files.sha256`](local_setup_v5_files.sha256): one line per file, relative to the package root |

## Reproduce and verify
```bash
git archive --format=zip --prefix=JSB_Local_Setup_v5/ -o JSB_Local_Setup_v5.zip \
  2057296f0e6b1511bc9d8a1c09b3bc0fad940dfc:candidate-assessment \
  local_load TABLE_INVENTORY.md exercise2-ingestion exercise3-schema-design dbt_jsb_assessment
sha256sum JSB_Local_Setup_v5.zip          # expect 4e900b9c…ed07356 with git 2.43
```
- **Different git versions** can compress differently. In that case, compare the files instead of
  the archive: unzip, `cd JSB_Local_Setup_v5`, then `sha256sum -c ../local_setup_v5_files.sha256`
  (all 93 must report OK).
- **Windows:** `certutil -hashfile JSB_Local_Setup_v5.zip SHA256`.

## Relation to v4
v4 (the package Codex ran on Windows XAMPP on 2026-09-29) was zipped by hand from the same source
files. v5 differs from it in exactly two ways:
- the six genuine Windows screenshots now under `local_load/screenshots/`;
- the provenance link at the top of `local_load/README.md`.

No SQL, dbt model, setup script or data file changed between them, so the Windows run
(`local_load/evidence/windows_xampp_run_20260929.md`) applies to v5 unchanged.
