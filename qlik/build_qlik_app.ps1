<#
.SYNOPSIS
    Builds the complete "Libstar Product Analytics" Qlik Sense Cloud app from the
    files in this folder: data upload, load script, reload, master measures, and
    the full visual layer (5 sheets, ~33 objects incl. a real SA province map).

.DESCRIPTION
    One-shot, idempotent rebuild. Re-running overwrites measures/objects in place
    (same qIds), so it doubles as a "reset the app design" script.

    Prerequisites:
      1. qlik-cli installed (https://github.com/qlik-oss/qlik-cli/releases) and on
         PATH, or pass -QlikExe with the full path to qlik.exe.
      2. An authenticated context:
           qlik context create libstar --server https://<tenant>.qlikcloud.com --api-key <key>
           qlik context use libstar
         (API key: tenant -> avatar -> Settings -> API keys -> Generate new key.
         Keys on this tenant have been observed to silently stop authenticating
         within hours - if `qlik status` errors "could not connect to engine /
         incorrect or no authorization credentials", generate a fresh one, don't
         assume the tooling is broken.)
      3. An existing (can be empty) app in the tenant; pass its ID as -AppId.
      4. The exported TXT files in qlik\upload\ if loading data for the first
         time (-UploadData) - see qlik\CODEX_HANDOFF.md for the Synapse firewall
         step that must happen first (temp-allow Qlik Cloud EU egress IPs).

.EXAMPLE
    .\build_qlik_app.ps1 -AppId ce620f1c-5ad7-4add-801f-20ce0c044326
    # measures + objects only (data already loaded)

.EXAMPLE
    .\build_qlik_app.ps1 -AppId <id> -UploadData
    # full build: upload upload\*.txt to DataFiles, set + run load script, then
    # measures + objects

.NOTES
    Gotchas baked into this script (full detail in ..\..\ (memory)\qlik-cli-automation.md
    and this project's own qlik\CODEX_HANDOFF.md):
      - qlik.exe misdetects stdin on Windows: every call is wrapped in cmd /c "... < NUL".
      - DataFiles rejects .tsv/.csv.gz extensions cleanly: files here are already .txt.
      - Sheets and the objects they reference MUST be posted in ONE object set call,
        or the CLI silently spawns unlinked duplicates. app_objects_combined.json is
        that single combined payload - never split it.
      - Measures need explicit qDec/qThou characters alongside qUseThou:1, or a
        format like "R# ##0" renders as the literal string "1170282306879R# ##0".
      - Every chart column needs a qDef.cId or the client renders a blank panel.
      - The map object (map-province-revenue) uses a different schema than normal
        charts: qInfo.qType "map", a top-level "gaLayers" array (not qHyperCubeDef
        directly), each layer with its own nested qHyperCubeDef + locationOrLatitude
        pointing at the [province] field. Hand-writing this schema is error-prone -
        it was generated correctly by asking Qlik's own Insight Advisor
        (`POST /v1/apps/<id>/insight-analyses/actions/recommend` with
        `{"text": "sum of prov_revenue_12m_zar by province as map"}`) and adapting
        its `recAnalyses[].options` output, rather than guessing the shape by hand.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$AppId,

    [string]$QlikExe = "qlik",

    [switch]$UploadData,

    [string]$UploadDir = "upload",

    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Invoke-Qlik {
    # NOTE: parameter must not be called $Args - that is a PowerShell automatic
    # variable and silently arrives empty, making qlik print its help text.
    param([string]$CommandLine)
    $out = cmd /c "`"$QlikExe`" $CommandLine < NUL" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "qlik $CommandLine failed:`n$out" }
    return $out
}

Write-Host "== Context check =="
Invoke-Qlik "context ls" | Write-Host

if (-not $VerifyOnly) {

    if ($UploadData) {
        Write-Host "== Uploading exports to DataFiles (already .txt) =="
        Get-ChildItem (Join-Path $here $UploadDir) -Filter *.txt | ForEach-Object {
            Write-Host "  $($_.Name) -> lib://DataFiles/$($_.Name)"
            Invoke-Qlik "data-file create --name $($_.Name) --file `"$($_.FullName)`""
        }

        Write-Host "== Setting load script and reloading =="
        Invoke-Qlik "app script set `"$(Join-Path $here 'libstar_load_script.qvs')`" --app $AppId"
        Invoke-Qlik "app reload --app $AppId" | Write-Host
    }

    Write-Host "== Master measures (9) =="
    Invoke-Qlik "app measure set `"$(Join-Path $here 'objects\measures.json')`" --app $AppId"

    Write-Host "== Visual layer: 5 sheets + ~28 child objects, ONE call (linking gotcha) =="
    Invoke-Qlik "app object set `"$(Join-Path $here 'objects\app_objects_combined.json')`" --app $AppId"
}

Write-Host "== Verification =="

# 1. Known-good total: Revenue 12m must reconcile with rpt.vw_kpi_summary
$kpi = Invoke-Qlik "app object data --app $AppId kpi-revenue"
Write-Host "  Revenue 12m KPI -> $($kpi | Select-Object -Last 1)"
if (-not ($kpi -match "1 170 282 306 879|1,170,282,306,879")) {
    Write-Warning "  Expected R1 170 282 306 879 (reconciled figure from CODEX_HANDOFF.md). Check the reload."
}

# 2. Sheet linking: cells[].name must still reference the named objects,
#    not short random strings (the silent-duplication failure mode)
foreach ($sheet in @("sheet-exec","sheet-catbrand","sheet-regional","sheet-dq","sheet-ml")) {
    $props = Invoke-Qlik "app object properties --app $AppId $sheet" | Out-String
    $names = ([regex]::Matches($props, '"name":\s*"([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
    $orphans = $names | Where-Object { $_ -notmatch '^(kpi|bar|line|pie|treemap|map|table|tbl|scatter|flt|txt)-' }
    if ($orphans) {
        Write-Warning "  $sheet has unlinked cells: $($orphans -join ', ') - repost app_objects_combined.json in ONE call"
    } else {
        Write-Host "  $sheet : $($names.Count) cells linked OK"
    }
}

# 3. Render prerequisites: every chart column needs a cId or the client shows a blank panel
$chartIds = @("pie-group","bar-brands","line-growth","treemap-cat","bar-cat-margin",
              "bar-cat-solution","tbl-brand-cat","bar-province-revenue","bar-province-skus",
              "bar-channel-revenue","bar-reject","tbl-kpi-recon","scatter-segments","tbl-anomalies")
foreach ($id in $chartIds) {
    $props = Invoke-Qlik "app object properties --app $AppId $id" | Out-String
    if ($props -notmatch '"cId"') {
        Write-Warning "  $id has no cId on its columns - it will render as a blank panel"
    }
}
Write-Host "  cId render check done ($($chartIds.Count) charts/tables)"

# 4. Map object: different schema, check gaLayers exists instead of qHyperCubeDef at top level
$mapProps = Invoke-Qlik "app object properties --app $AppId map-province-revenue" | Out-String
if ($mapProps -notmatch '"gaLayers"') {
    Write-Warning "  map-province-revenue has no gaLayers - the geo area layer did not save correctly"
} else {
    Write-Host "  map-province-revenue : gaLayers present OK"
}

Write-Host ""
Write-Host "Build complete. Open the app and hard-refresh (Ctrl+F5) any tab that was already open."
