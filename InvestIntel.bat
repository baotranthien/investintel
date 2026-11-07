@echo off
:: ===================================================================
:: InvestIntel 1-Click Desktop Launcher
:: Tự động khởi chạy cả Backend (FastAPI :8000) và Frontend (Next.js :3000)
:: ===================================================================
title InvestIntel Terminal — 1-Click Launcher
cd /d "%~dp0"
if exist "%~dp0InvestIntel.exe" (
    "%~dp0InvestIntel.exe" %*
) else (
    echo [!] Khong tim thay InvestIntel.exe, khoi dong qua PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local\start-investintel.ps1"
)

