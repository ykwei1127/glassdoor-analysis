[CmdletBinding()]
param(
    [int]$Port = 9223,
    [int]$MaxExtractions
)

$ErrorActionPreference = "Stop"
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "找不到 .venv。請先依照 QUICK_START.md 完成環境設定。"
}

$requiredFiles = @(
    ".\artifacts\reviews_aggregate.json",
    ".\artifacts\region_pool.json",
    ".\artifacts\company_region_review_urls.json"
)
$missingFiles = $requiredFiles | Where-Object { -not (Test-Path $_) }
if ($missingFiles) {
    throw "找不到既有資料檔案：$($missingFiles -join ', ')。請確認目前位於 handoff 根目錄。"
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 5 | Out-Null
} catch {
    throw "Chrome Debug Port $Port 尚未啟動。請先執行 .\scripts\start_chrome_cdp.ps1 並登入 Glassdoor。"
}

$backupName = "artifacts_backup_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss")
Write-Output "正在備份目前資料到 $backupName ..."
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
        throw "MaxExtractions 必須是 0 或更大的數字。"
    }
    $arguments += @("--max-extractions", $MaxExtractions)
}

Write-Output "只更新既有公司／地區評分，不會更新 office locations 或 review URL。"
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "評分更新失敗。請保留 artifacts 與備份資料，查看上方錯誤訊息。"
}

Write-Output "既有評分更新完成。"
Write-Output "目前資料在 .\artifacts；更新前備份在 .\$backupName。"
