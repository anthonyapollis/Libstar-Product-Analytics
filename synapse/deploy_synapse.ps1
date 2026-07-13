# Deploy Synapse serverless SQL objects for the Libstar reporting layer.
# Uses SQL admin credentials from ..\.secrets\synapse_sql_admin.txt and
# generates qlik_reader / master key passwords on first run.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$secrets = Join-Path (Split-Path -Parent $here) ".secrets"
$server = "syn-pargoparcels-ondemand.sql.azuresynapse.net"
$adminUser = "pargoadmin"
$adminPwd = (Get-Content (Join-Path $secrets "synapse_sql_admin.txt") -Raw).Trim()

function New-AlnumPassword {
    $chars = [char[]]('ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'.ToCharArray())
    return "Zx9" + (-join ((1..18) | ForEach-Object { $chars | Get-Random })) + "w4"
}

$qlikPwdFile = Join-Path $secrets "qlik_reader.txt"
if (-not (Test-Path $qlikPwdFile)) { (New-AlnumPassword) | Out-File $qlikPwdFile -NoNewline }
$qlikPwd = (Get-Content $qlikPwdFile -Raw).Trim()

$mkPwdFile = Join-Path $secrets "synapse_master_key.txt"
if (-not (Test-Path $mkPwdFile)) { (New-AlnumPassword) | Out-File $mkPwdFile -NoNewline }
$mkPwd = (Get-Content $mkPwdFile -Raw).Trim()

Write-Host "deploying master objects (database + login)..."
sqlcmd -S $server -d master -U $adminUser -P $adminPwd -b -l 60 `
    -i (Join-Path $here "01_master_setup.sql") -v QLIK_READER_PWD=$qlikPwd
if ($LASTEXITCODE -ne 0) { throw "master setup failed" }

Write-Host "deploying libstar reporting objects..."
sqlcmd -S $server -d libstar -U $adminUser -P $adminPwd -b -l 60 `
    -i (Join-Path $here "02_libstar_objects.sql") -v MASTER_KEY_PWD=$mkPwd
if ($LASTEXITCODE -ne 0) { throw "libstar objects failed" }

Write-Host "done. Qlik connects to $server / db libstar as qlik_reader (password in .secrets\qlik_reader.txt)"
