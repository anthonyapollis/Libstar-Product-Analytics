# Check Azure spend against the $200 trial credit.
# The Cost Management API is heavily throttled on free-trial subscriptions,
# so this retries with backoff and falls back to the consumption usage API.

$sub = "cea67e6f-62b2-4b2f-83e8-9af31093d8c8"
$creditUsd = 200.0

$bodyFile = Join-Path $env:TEMP "pargo_costquery.json"
'{"type":"ActualCost","timeframe":"BillingMonthToDate","dataset":{"granularity":"None","aggregation":{"totalCost":{"name":"Cost","function":"Sum"}}}}' |
    Out-File $bodyFile -Encoding utf8
$url = "https://management.azure.com/subscriptions/$sub/providers/Microsoft.CostManagement/query?api-version=2023-11-01"

$result = $null
foreach ($delay in 0, 30, 90, 180) {
    if ($delay -gt 0) { Start-Sleep -Seconds $delay }
    $raw = az rest --method post --headers "Content-Type=application/json" --url $url --body "@$bodyFile" -o json 2>$null
    if ($LASTEXITCODE -eq 0 -and $raw) { $result = $raw | ConvertFrom-Json; break }
    Write-Host "cost query throttled, retrying in a bit..."
}

if ($result -and $result.properties.rows.Count -gt 0) {
    $cost = [math]::Round([double]$result.properties.rows[0][0], 2)
    $currency = $result.properties.rows[0][1]
    $pct = [math]::Round($cost / $creditUsd * 100, 1)
    Write-Host "Month-to-date spend: $cost $currency (~$pct% of `$$creditUsd trial credit)"
    if ($pct -ge 75) { Write-Host "WARNING: over 75% of trial credit used - wind down or pause resources." -ForegroundColor Red }
    elseif ($pct -ge 50) { Write-Host "CAUTION: over half the trial credit used." -ForegroundColor Yellow }
} elseif ($result) {
    Write-Host "Cost query returned no rows yet (trial cost data lags ~24h)."
} else {
    Write-Host "Cost Management API still throttled. Falling back to consumption usage list..."
    $usage = az consumption usage list --top 1000 -o json 2>$null | ConvertFrom-Json
    if ($usage) {
        $total = ($usage | Measure-Object -Property pretaxCost -Sum).Sum
        Write-Host ("Approx billed usage this period: {0:N2} (pretax)" -f $total)
    } else {
        Write-Host "No cost data available via API. Check https://portal.azure.com > Cost Management, or rely on the pargo-trial-budget email alerts (50/75/90% actual, 100% forecast)."
    }
}
