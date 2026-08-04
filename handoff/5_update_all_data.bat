@echo off
setlocal
cd /d "%~dp0"
title Glassdoor Handoff - Full Data Update

echo This will update office locations, the region pool, review URLs,
echo new ratings, and existing ratings.
echo.
choice /C YN /N /M "Continue with the full data update? [Y/N] "
if errorlevel 2 (
    echo Cancelled.
    pause
    exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_data.ps1" -RefreshExisting
if errorlevel 1 (
    echo.
    echo The full update failed. Please keep the backup and check the message above.
    pause
    exit /b 1
)

echo.
echo The full data update completed.
pause
