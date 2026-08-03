[CmdletBinding()]
param(
    [int]$Port = 9223,
    [switch]$RefreshExisting
)

$ErrorActionPreference = "Stop"
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "找不到 .venv。請先依照使用說明完成環境設定。"
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 5 | Out-Null
} catch {
    throw "Chrome Debug Port $Port 尚未啟動。請先執行 .\scripts\start_chrome_cdp.ps1 並登入 Glassdoor。"
}

$backupName = "artifacts_backup_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss")
Write-Output "正在備份目前資料到 $backupName ..."
Copy-Item "artifacts" $backupName -Recurse -ErrorAction Stop

function Invoke-GlassdoorStage {
    param([string[]]$Arguments)
    & $python -m glassdoor_analysis @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "資料更新中止，最後執行的階段失敗。請保留目前 artifacts 與備份資料，查看上方錯誤訊息。"
    }
}

$common = @(
    "--browser-cdp-url", "http://127.0.0.1:$Port",
    "--output-dir", ".\artifacts"
)

Write-Output "正在更新公司辦公室與地區池..."
Invoke-GlassdoorStage (@("--stage", "discover-locations", "--rebuild-region-pool") + $common)

Write-Output "正在補充新的公司／地區 review URL..."
Invoke-GlassdoorStage (@("--stage", "resolve-review-urls") + $common)

Write-Output "正在抓取尚未成功的新資料..."
Invoke-GlassdoorStage (@("--stage", "extract-metrics") + $common)

if ($RefreshExisting) {
    Write-Output "正在重新抓取既有公司／地區的最新評分..."
    Invoke-GlassdoorStage (@("--stage", "extract-metrics", "--refresh-existing-metrics") + $common)
}

Write-Output "資料更新完成。"
Write-Output "目前資料在 .\artifacts；更新前備份在 .\$backupName。"
