@echo off
setlocal
cd /d "%~dp0"
title Glassdoor Handoff - Start Chrome

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_chrome_cdp.ps1"
if errorlevel 1 (
    echo.
    echo Chrome could not be started. Please check the message above.
    pause
    exit /b 1
)

echo.
echo Chrome is ready. Log in to Glassdoor in the new Chrome window.
pause
