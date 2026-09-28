@echo off
rem ===========================================================================
rem  JSB assessment: set up the project on your local XAMPP MariaDB, then run dbt
rem  step by step so you can see what each step builds.
rem
rem    Step 1  load the 29 base tables (the source data)     -> jsb_assessment, jsb_platform
rem    Step 2  install dbt in a private Python environment   (first run only)
rem    Step 3  dbt debug   : check dbt can reach the database
rem    Step 4  dbt run     : staging layer, 11 views         -> jsb_platform_staging
rem    Step 5  dbt run     : marts layer, 13 tables          -> jsb_platform_marts
rem    Step 6  dbt test    : 54 data tests
rem
rem  Needs: XAMPP MySQL/MariaDB running on port 3306 (root, no password), Python 3.9-3.11.
rem  Re-running is safe for a demo but resets the 29 base tables to the submission data.
rem ===========================================================================
setlocal
cd /d "%~dp0"
set "HERE=%CD%"
set "PROJECT=%HERE%\..\dbt_jsb_assessment"
set "VENV=%HERE%\.dbt-venv"

rem --- find the XAMPP mysql client --------------------------------------------
set "MYSQL="
if defined XAMPP_MYSQL set "MYSQL=%XAMPP_MYSQL%"
if not defined MYSQL for %%D in (C:\xampp C:\xampp3 C:\xampp001 C:\xampp101) do (
    if not defined MYSQL if exist "%%D\mysql\bin\mysql.exe" set "MYSQL=%%D\mysql\bin\mysql.exe"
)
if not defined MYSQL (
    echo Could not find mysql.exe. Set XAMPP_MYSQL to its full path and run again, e.g.
    echo   set XAMPP_MYSQL=C:\xampp\mysql\bin\mysql.exe
    exit /b 1
)
echo Using %MYSQL%
echo.

echo === Step 1 of 6: load the 29 base tables =====================================
echo These are the source data: the two Exercise 1 files, the Exercise 2 API load and
echo run log, and the Exercise 3 schema with its sample data.
"%MYSQL%" -u root --protocol=TCP -P 3306 --default-character-set=utf8mb4 < "%HERE%\01_load_submission_tables.sql" || goto :failed
echo.
echo Look in Workbench: databases jsb_assessment (6 tables) and jsb_platform (23 tables).
pause

echo === Step 2 of 6: install dbt (first run only) =================================
if exist "%VENV%\Scripts\dbt.exe" (
    echo dbt is already installed in %VENV%
) else (
    set "PY="
    py -3.11 -c "" >nul 2>&1 && set "PY=py -3.11"
    if not defined PY py -3.10 -c "" >nul 2>&1 && set "PY=py -3.10"
    if not defined PY py -3.9 -c "" >nul 2>&1 && set "PY=py -3.9"
    if not defined PY python -c "" >nul 2>&1 && set "PY=python"
    if not defined PY (
        echo Python not found. Install Python 3.11 from python.org, then run this again.
        exit /b 1
    )
    call :install
    if errorlevel 1 goto :failed
)
set "DBT=%VENV%\Scripts\dbt.exe"
cd /d "%PROJECT%"
set "DBT_PROFILES_DIR=%PROJECT%"
echo.

echo === Step 3 of 6: dbt debug ====================================================
echo dbt reads profiles.yml (target "xampp") and checks it can connect.
"%DBT%" debug --target xampp || goto :failed
pause

echo === Step 4 of 6: dbt run --select staging =====================================
echo Staging = one VIEW per source table: renamed, typed, references normalised.
echo Views store no data, so nothing is duplicated; they read the base tables live.
"%DBT%" run --select staging --target xampp || goto :failed
echo.
echo Look in Workbench: jsb_platform_staging (11 views, e.g. stg_internal_deposits).
echo The SQL dbt ran is in dbt_jsb_assessment\target\run\jsb_assessment\models\staging\
pause

echo === Step 5 of 6: dbt run --select marts =======================================
echo Marts = the reporting tables built from staging: star schema (dim_/fact_),
echo the reconciliation (fct_recon_exceptions, mart_recon_bridge) and query marts.
"%DBT%" run --select marts --target xampp || goto :failed
echo.
echo Look in Workbench: jsb_platform_marts (13 tables, each with a primary key). Power BI reads these.
pause

echo === Step 6 of 6: dbt test =====================================================
echo 54 tests: unique / not-null keys, allowed categories, the R0.00 bridge,
echo no source row dropped, and wallet balance cache = ledger.
"%DBT%" test --target xampp || goto :failed
echo.
echo Done. Next time, "dbt build --target xampp" does steps 4 to 6 in one command:
echo   cd "%PROJECT%"
echo   set DBT_PROFILES_DIR=.
echo   "%DBT%" build --target xampp
exit /b 0

:install
echo Creating a private Python environment with %PY% ...
%PY% -m venv "%VENV%" || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install --quiet "dbt-core==1.7.*" "dbt-mysql==1.7.*" || exit /b 1
echo dbt installed.
exit /b 0

:failed
echo.
echo *** A step failed: see the message above. Nothing after it was run. ***
exit /b 1
