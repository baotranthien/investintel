@echo off
setlocal
cd /d "%~dp0"
echo Starting InvestIntel Local Platform...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local\start-investintel.ps1" %*
endlocal

