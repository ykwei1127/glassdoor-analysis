@echo off
setlocal
cd /d "%~dp0"
title Glassdoor Handoff - Setup Environment

echo ========================================
echo  Glassdoor handoff - first-time setup
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Please install Python 3.11 or newer first.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo Node.js was not found. Please install Node.js 18 or newer first.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo npm was not found. Please reinstall Node.js with npm included.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create the Python environment.
        pause
        exit /b 1
    )
)

echo Installing the Python project...
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 (
    echo Python installation failed. Please check the error above.
    pause
    exit /b 1
)

echo Installing the browser connection library...
npm install --ignore-scripts
if errorlevel 1 (
    echo Node.js dependency installation failed. Please check the error above.
    pause
    exit /b 1
)

echo.
echo Setup completed. You can close this window.
pause
