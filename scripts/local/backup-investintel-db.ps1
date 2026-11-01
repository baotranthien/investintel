# scripts/local/backup-investintel-db.ps1
# InvestIntel Local SQLite Database Hot Backup
[CmdletBinding()]
param(
    [string]$Description = "Manual backup via CLI",
    [switch]$ApplyRetention
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pyExe)) {
    Write-Host "ERROR: Python virtual environment not found at $pyExe" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "                INVESTINTEL LOCAL SQLITE HOT BACKUP                " -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green

$env:PYTHONPATH = $ProjectRoot
$retArg = if ($ApplyRetention) { "True" } else { "False" }

& $pyExe -c "
import sys, json
from pathlib import Path
from services.db.backup import create_backup, apply_retention_policy

try:
    manifest = create_backup(description='$Description')
    print('SUCCESS:' + json.dumps(manifest))
    if ${retArg}:
        deleted = apply_retention_policy()
        if deleted:
            print('RETENTION_DELETED:' + json.dumps(deleted))
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(1)
" | ForEach-Object {
    if ($_ -like "SUCCESS:*") {
        $data = $_.Substring(8) | ConvertFrom-Json
        Write-Host "Backup Created Successfully!" -ForegroundColor Green
        Write-Host "  File       : $($data.backup_filename)" -ForegroundColor White
        Write-Host "  Path       : $($data.backup_path)" -ForegroundColor DarkGray
        Write-Host "  Size       : $([math]::Round($data.backup_size_bytes / 1MB, 2)) MB" -ForegroundColor White
        Write-Host "  SHA-256    : $($data.sha256)" -ForegroundColor DarkCyan
        Write-Host "  Tables     : $($data.tables_count) tables verified" -ForegroundColor White
        Write-Host "  Duration   : $($data.duration_sec)s" -ForegroundColor White
        Write-Host "  Integrity  : $($data.integrity)" -ForegroundColor Green
    } elseif ($_ -like "RETENTION_DELETED:*") {
        $del = $_.Substring(18) | ConvertFrom-Json
        Write-Host "  Retention  : Pruned old backups ($($del -join ', '))" -ForegroundColor Yellow
    } elseif ($_ -like "ERROR:*") {
        Write-Host "BACKUP FAILED: $($_.Substring(6))" -ForegroundColor Red
        exit 1
    } else {
        Write-Host $_ -ForegroundColor DarkGray
    }
}
Write-Host ""
