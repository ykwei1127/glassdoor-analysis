[CmdletBinding()]
param(
    [int]$Port = 9223,
    [int]$MaxExtractions,
    [int]$ProgressEvery = 1
)

$ErrorActionPreference = "Stop"
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python environment not found. Run 1_setup_environment.bat first."
}

$requiredFiles = @(
    ".\artifacts\reviews_aggregate.json",
    ".\artifacts\region_pool.json",
    ".\artifacts\company_region_review_urls.json"
)
$missingFiles = $requiredFiles | Where-Object { -not (Test-Path $_) }
if ($missingFiles) {
    throw "Required data files are missing: $($missingFiles -join ', '). Make sure you are running this from the handoff folder."
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 5 | Out-Null
} catch {
    throw "Chrome Debug Port $Port is not running. Run 2_start_chrome_cdp.bat and log in to Glassdoor first."
}

$backupName = "artifacts_backup_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss")
Write-Output "Backing up current data to $backupName ..."
Copy-Item "artifacts" $backupName -Recurse -ErrorAction Stop

$arguments = @(
    "-m", "glassdoor_analysis",
    "--stage", "extract-metrics",
    "--refresh-existing-metrics",
    "--browser-cdp-url", "http://127.0.0.1:$Port",
    "--output-dir", ".\artifacts"
)
if ($PSBoundParameters.ContainsKey("MaxExtractions")) {
    if ($MaxExtractions -lt 0) {
        throw "MaxExtractions must be zero or greater."
    }
    $arguments += @("--max-extractions", $MaxExtractions)
}
if ($ProgressEvery -lt 1) {
    throw "ProgressEvery must be one or greater."
}
$arguments += @("--progress-every", $ProgressEvery)

Write-Output "Refreshing existing company-region ratings only."
Write-Output "Office locations and review URLs will not be updated."
Write-Output "Progress will be shown after every $ProgressEvery record."
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "The ratings refresh failed. Keep the backup and review the error message above."
}

Write-Output "Existing ratings refresh completed."
Write-Output "Current data: .\artifacts"
Write-Output "Backup: .\$backupName"
