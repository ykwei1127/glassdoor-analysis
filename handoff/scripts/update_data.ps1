[CmdletBinding()]
param(
    [int]$Port = 9223,
    [switch]$RefreshExisting
)

$ErrorActionPreference = "Stop"
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python environment not found. Run 1_setup_environment.bat first."
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 5 | Out-Null
} catch {
    throw "Chrome Debug Port $Port is not running. Run 2_start_chrome_cdp.bat and log in to Glassdoor first."
}

$backupName = "artifacts_backup_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss")
Write-Output "Backing up current data to $backupName ..."
Copy-Item "artifacts" $backupName -Recurse -ErrorAction Stop

function Invoke-GlassdoorStage {
    param([string[]]$Arguments)
    & $python -m glassdoor_analysis @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "The data update stopped because a stage failed. Keep the artifacts and backup, then review the error above."
    }
}

$common = @(
    "--browser-cdp-url", "http://127.0.0.1:$Port",
    "--output-dir", ".\artifacts"
)

Write-Output "Updating office locations and the region pool..."
Invoke-GlassdoorStage (@("--stage", "discover-locations", "--rebuild-region-pool") + $common)

Write-Output "Finding new company-region review URLs..."
Invoke-GlassdoorStage (@("--stage", "resolve-review-urls") + $common)

Write-Output "Extracting new ratings..."
Invoke-GlassdoorStage (@("--stage", "extract-metrics") + $common)

if ($RefreshExisting) {
    Write-Output "Refreshing existing company-region ratings..."
    Invoke-GlassdoorStage (@("--stage", "extract-metrics", "--refresh-existing-metrics") + $common)
}

Write-Output "Full data update completed."
Write-Output "Current data: .\artifacts"
Write-Output "Backup: .\$backupName"
