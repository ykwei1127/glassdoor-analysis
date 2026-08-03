[CmdletBinding(SupportsShouldProcess)]
param(
    [int]$Port = 9223,
    [string]$UserDataDir = (Join-Path $env:LOCALAPPDATA "glassdoor-analysis\chrome-cdp-profile"),
    [string]$ChromePath
)

$ErrorActionPreference = "Stop"

if (-not $ChromePath) {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
    )
    $ChromePath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $ChromePath -or -not (Test-Path $ChromePath)) {
    throw "Chrome executable not found. Pass -ChromePath 'C:\\Path\\to\\chrome.exe'."
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be between 1 and 65535."
}

$existing = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Chrome CDP may already be listening at http://127.0.0.1:$Port"
    Write-Output "Verify it with: Invoke-WebRequest http://127.0.0.1:$Port/json/version"
    exit 0
}

New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null
$arguments = @(
    "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=$Port",
    "--user-data-dir=$UserDataDir"
)

if ($PSCmdlet.ShouldProcess($ChromePath, "Start Chrome with CDP port $Port")) {
    Start-Process -FilePath $ChromePath -ArgumentList $arguments | Out-Null
    Write-Output "Started Chrome with CDP at http://127.0.0.1:$Port"
    Write-Output "Profile: $UserDataDir"
    Write-Output "Log in to Glassdoor in this Chrome window before running the scraper."
    Write-Output "Verify it with: Invoke-WebRequest http://127.0.0.1:$Port/json/version"
}
