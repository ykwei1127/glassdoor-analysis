@echo off
set "HANDOFF_DIR=%~dp0"
start "Glassdoor Handoff PowerShell" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath $env:HANDOFF_DIR"
