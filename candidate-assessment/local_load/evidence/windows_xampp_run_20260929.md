# Windows XAMPP MariaDB validation run

- **Run date:** 2026-09-29, Africa/Johannesburg
- **Host:** Windows 10 22H2; local XAMPP service on `127.0.0.1:3306`
- **Server:** `10.4.24-MariaDB`
- **dbt:** dbt-core `1.7.20`; adapter `mariadb 1.7.0`; Python `3.11.3`
- **Source package:** `JSB_Local_Setup_v4`, `local_load/setup_local.bat`

This is an independent Codex validation on the local XAMPP instance after the old JSB schemas were removed. It is not a container-only result.

## Results

| Step | Command/action | Observed result |
|---|---|---|
| 1 | `setup_local.bat` Step 1 | Loaded 326 `internal_deposits`, 306 `gateway_settlement`, 1,024 `transactions`, 4 `ingest_runs`, 1 `ingest_rejects`, and 24 `jsb_platform` tables. |
| 2 | `dbt debug --target xampp` | Connection to `127.0.0.1:3306` succeeded; profile/project valid; “All checks passed!”. |
| 3 | `dbt run --select staging --target xampp` | 11/11 staging views built successfully. |
| 4 | `dbt run --select marts --full-refresh --target xampp` | 13/13 marts built successfully, including 2 incremental models. |
| 5 | `dbt test --target xampp` | **PASS=54, WARN=0, ERROR=0, SKIP=0, TOTAL=54**. |
| 6 | `information_schema.tables` count query | `jsb_assessment`: 6 tables; `jsb_platform`: 24 tables; `jsb_platform_marts`: 13 tables; `jsb_platform_staging`: 11 views; total **43 tables + 11 views = 54 objects**. |
| 7 | key inventory query | **0 tables without a primary key**. |
| 8 | local dbt reconciliation mart | 317 reconciled rows; **274 exact matches**; bridge residual **0.00**. |

## Commands used after the batch file’s interactive Step 1 pause

```bat
cd C:\Users\Anthony.DESKTOP-ES5HL78\Downloads\JSB_Local_Setup_v4\dbt_jsb_assessment
set DBT_PROFILES_DIR=.
..\local_load\.dbt-venv\Scripts\dbt.exe debug --target xampp
..\local_load\.dbt-venv\Scripts\dbt.exe run --select staging --target xampp
..\local_load\.dbt-venv\Scripts\dbt.exe run --select marts --full-refresh --target xampp
..\local_load\.dbt-venv\Scripts\dbt.exe test --target xampp
```

## Remaining visual evidence

The run above is genuine local execution proof. Add the requested MySQL Workbench/terminal screenshots and link their SHA-256 values in the final evidence manifest; this Markdown log does not substitute for those captures.