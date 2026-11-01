# scripts/local/restore-investintel-db.ps1
# InvestIntel Local SQLite Database Point-in-Time Restore
[CmdletBinding()]
param(
    [string]$BackupFile,
    [switch]$Latest,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackupDir = Join-Path $ProjectRoot "data\backups"

if (-not (Test-Path $pyExe)) {
    Write-Host "ERROR: Python virtual environment not found at $pyExe" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "               INVESTINTEL LOCAL SQLITE DB RESTORE                 " -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan

$env:PYTHONPATH = $ProjectRoot

# If no backup file specified and not -Latest, list available backups
if (-not $BackupFile -and -not $Latest) {
    Write-Host "Available Backups in ${BackupDir}:" -ForegroundColor Yellow
    & $pyExe -c "
import json
from services.db.backup import list_backups
backups = list_backups()
if not backups:
    print('NO_BACKUPS')
else:
    print('LIST:' + json.dumps(backups))
" | ForEach-Object {
        if ($_ -eq "NO_BACKUPS") {
            Write-Host "  No backups found in $BackupDir. Create one using scripts\local\backup-investintel-db.ps1" -ForegroundColor Yellow
        } elseif ($_ -like "LIST:*") {
            $list = $_.Substring(5) | ConvertFrom-Json
            $i = 1
            foreach ($b in $list) {
                $mb = [math]::Round($b.backup_size_bytes / 1MB, 2)
                Write-Host "  [$i] $($b.backup_filename) ($mb MB, $($b.timestamp), integrity: $($b.integrity))" -ForegroundColor White
                $i++
            }
            Write-Host ""
            Write-Host "To restore, run: .\scripts\local\restore-investintel-db.ps1 -BackupFile <filename> [-Force]" -ForegroundColor Cyan
            Write-Host "Or to restore the latest backup: .\scripts\local\restore-investintel-db.ps1 -Latest [-Force]" -ForegroundColor Cyan
        }
    }
    Write-Host ""
    exit 0
}

# Resolve target backup file
$targetPath = ""
if ($Latest) {
    $backups = Get-ChildItem -Path $BackupDir -Filter "investintel_*.db" | Sort-Object LastWriteTime -Descending
    if ($backups.Count -eq 0) {
        Write-Host "ERROR: No backup files found in $BackupDir" -ForegroundColor Red
        exit 1
    }
    $targetPath = $backups[0].FullName
    Write-Host "Selected latest backup: $($backups[0].Name)" -ForegroundColor Yellow
} else {
    if (Test-Path $BackupFile) {
        $targetPath = (Resolve-Path $BackupFile).Path
    } else {
        $check = Join-Path $BackupDir $BackupFile
        if (Test-Path $check) {
            $targetPath = $check
        } else {
            Write-Host "ERROR: Backup file not found: $BackupFile" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host "Target Backup: $targetPath" -ForegroundColor White
Write-Host "Active DB: $(Join-Path $ProjectRoot 'data\trading.db')" -ForegroundColor White
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Are you sure you want to restore this backup over the active database? (yes/no)"
    if ($confirm -ne "yes" -and $confirm -ne "y") {
        Write-Host "Restore canceled by user." -ForegroundColor Yellow
        exit 0
    }
}

& $pyExe -c "
import sys, json
from pathlib import Path
from services.db.backup import restore_backup

try:
    res = restore_backup(backup_path=Path(r'$targetPath'))
    print('SUCCESS:' + json.dumps(res))
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(1)
" | ForEach-Object {
    if ($_ -like "SUCCESS:*") {
        $res = $_.Substring(8) | ConvertFrom-Json
        Write-Host "Database Restored Successfully!" -ForegroundColor Green
        Write-Host "  Source Backup : $($res.backup_path)" -ForegroundColor White
        Write-Host "  Target DB     : $($res.target_db_path)" -ForegroundColor White
        Write-Host "  Safety Backup : $($res.safety_snapshot_path)" -ForegroundColor DarkCyan
        Write-Host "  Tables        : $($res.tables_count) verified" -ForegroundColor White
        Write-Host "  Post-Integrity: $($res.integrity)" -ForegroundColor Green
    } elseif ($_ -like "ERROR:*") {
        Write-Host "RESTORE FAILED: $($_.Substring(6))" -ForegroundColor Red
        exit 1
    } else {
        Write-Host $_ -ForegroundColor DarkGray
    }
}
Write-Host ""
