@echo off
setlocal
cd /d "%~dp0"
title Glassdoor Handoff - Refresh Existing Ratings

echo This will refresh existing company-region ratings only.
echo It will not update the office locations or region pool.
echo.
choice /C YN /N /M "Continue with the full existing-ratings refresh? [Y/N] "
if errorlevel 2 (
    echo Cancelled.
    pause
    exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\refresh_existing_metrics.ps1"
if errorlevel 1 (
    echo.
    echo The refresh failed. Please keep the backup and check the message above.
    pause
    exit /b 1
)

echo.
echo The existing-ratings refresh completed.
pause
