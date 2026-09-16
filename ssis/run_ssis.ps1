<#
.SYNOPSIS
  Configure and run the Biml-generated Libstar SSIS packages, then reconcile the result.

.DESCRIPTION
  -Configure  writes this machine's folder locations to etl.Config (the packages read them when
              their RawFolder/WorkFolder/ReferenceFolder parameters are left empty).
  default     runs a package from the built Libstar.ispac with DTExec and prints etl.PackageRun plus
              the reconciliation views, to compare with the Azure Data Factory result:
              raw 5,014,409 | clean 4,284,971 | quarantined 729,438.

  DTExec needs the Integration Services feature of SQL Server (Standard edition or higher, or
  Developer). Without it, run LIB_Master.dtsx from Visual Studio instead (right-click > Execute
  Package); the -Configure step and the reconciliation queries still apply.

  Prerequisites
    1. sqlcmd -S localhost -E -i sql\00_setup_Libstar_SSIS.sql
    2. Open Libstar.SSIS.sln in Visual Studio (SSDT + BimlExpress), right-click Libstar_SSIS.biml >
       Generate SSIS Packages, then Build (produces Libstar.SSIS\bin\Development\Libstar.ispac).

.EXAMPLE
  .\run_ssis.ps1 -Configure          # once per machine
  .\run_ssis.ps1                     # LIB_Master: all four stages
  .\run_ssis.ps1 -ReconcileOnly      # just print the results of the last run
#>
param(
    [string]$Package = 'LIB_Master.dtsx',
    [string]$Server = 'localhost',
    [switch]$Configure,
    [switch]$ReconcileOnly,
    [string]$DTExec = 'C:\Program Files\Microsoft SQL Server\140\DTS\Binn\DTExec.exe'
)
$ErrorActionPreference = 'Stop'
$ssis = $PSScriptRoot
$repo = Split-Path $ssis

if ($Configure) {
    $rows = @{ RawFolder = (Join-Path $repo 'data\raw'); WorkFolder = (Join-Path $ssis 'work'); ReferenceFolder = (Join-Path $repo 'data\reference') }
    foreach ($k in $rows.Keys) {
        $v = $rows[$k].Replace("'", "''")
        sqlcmd -S $Server -E -d Libstar_SSIS -b -Q "MERGE etl.Config AS t USING (SELECT '$k' AS ConfigKey, N'$v' AS ConfigValue) AS s ON t.ConfigKey = s.ConfigKey WHEN MATCHED THEN UPDATE SET ConfigValue = s.ConfigValue, UpdatedAt = SYSDATETIME() WHEN NOT MATCHED THEN INSERT (ConfigKey, ConfigValue) VALUES (s.ConfigKey, s.ConfigValue);" | Out-Null
        Write-Host ("etl.Config {0,-16} = {1}" -f $k, $rows[$k])
    }
    return
}

$exit = 0
if (-not $ReconcileOnly) {
    $ispac = Join-Path $ssis 'Libstar.SSIS\bin\Development\Libstar.ispac'
    if (-not (Test-Path $ispac)) { throw "Build the project first: $ispac not found" }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & $DTExec /Project $ispac /Package $Package /Reporting EW
    $exit = $LASTEXITCODE
    $sw.Stop()
    Write-Host ("`n{0} finished with DTExec exit code {1} (0 = success) in {2:n1} min" -f $Package, $exit, $sw.Elapsed.TotalMinutes)
}

$q = @"
SET NOCOUNT ON;
SELECT TOP 6 RunId, PackageName, Status, RowsRead, RowsWritten, RowsRejected,
       DATEDIFF(second, StartTime, EndTime) AS Seconds, LEFT(Message, 200) AS Message
FROM etl.PackageRun ORDER BY RunId DESC;
SELECT * FROM dw.vw_kpi_summary;
SELECT reject_reason, row_count FROM dq.vw_reject_summary ORDER BY row_count DESC;
"@
sqlcmd -S $Server -E -d Libstar_SSIS -W -s " | " -Q $q
exit $exit
