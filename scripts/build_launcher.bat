@echo off
setlocal
echo [*] Compiling InvestIntel.exe with Microsoft .NET Framework C# Compiler...
set CSC="C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist %CSC% (
    echo [ERROR] csc.exe not found at %CSC%
    exit /b 1
)
%CSC% /nologo /target:exe /out:"%~dp0..\InvestIntel.exe" "%~dp0launcher\Program.cs"
if %ERRORLEVEL% EQU 0 (
    echo [OK] InvestIntel.exe compiled successfully.
) else (
    echo [ERROR] Compilation failed.
    exit /b 1
)

