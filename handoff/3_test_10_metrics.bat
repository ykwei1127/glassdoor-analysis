@echo off
setlocal
cd /d "%~dp0"
title Glassdoor Handoff - Test 10 Ratings

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\refresh_existing_metrics.ps1" -MaxExtractions 10
if errorlevel 1 (
    echo.
    echo The 10-record test failed. Please keep the backup and check the message above.
    pause
    exit /b 1
)

echo.
echo The 10-record test completed. Review the output above before running the full refresh.
pause
