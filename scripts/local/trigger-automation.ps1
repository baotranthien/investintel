# scripts/local/trigger-automation.ps1
# InvestIntel Local Background Automation CLI
[CmdletBinding()]
param(
    [switch]$Status,
    [switch]$Pause,
    [switch]$Resume,
    [switch]$RunPipeline,
    [string[]]$Symbols = @("FPT", "BMP")
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$env:PYTHONPATH = $ProjectRoot

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "           INVESTINTEL LOCAL BACKGROUND AUTOMATION CLI             " -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan

if ($Pause) {
    & $pyExe -c "
from services.scheduler.engine import local_scheduler
local_scheduler.pause()
print('SCHEDULER_PAUSED')
"
    Write-Host "Scheduler Paused successfully." -ForegroundColor Yellow
    exit 0
}

if ($Resume) {
    & $pyExe -c "
from services.scheduler.engine import local_scheduler
local_scheduler.resume()
print('SCHEDULER_RESUMED')
"
    Write-Host "Scheduler Resumed successfully." -ForegroundColor Green
    exit 0
}

if ($RunPipeline) {
    Write-Host "Triggering automated local pipeline (Ingestion -> Opportunity -> Alerts -> Backup)..." -ForegroundColor Yellow
    & $pyExe -c "
import asyncio, json, sys
from services.scheduler.engine import local_scheduler

async def main():
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ['FPT', 'BMP']
    res = await local_scheduler.run_pipeline(target_symbols=symbols)
    print('RESULT:' + json.dumps(res))

asyncio.run(main())
" @Symbols | ForEach-Object {
        if ($_ -like "RESULT:*") {
            $data = $_.Substring(7) | ConvertFrom-Json
            Write-Host "Pipeline Finished: $($data.pipeline_status)" -ForegroundColor Green
            Write-Host "  Duration: $($data.total_duration_sec)s" -ForegroundColor White
            Write-Host "  Stages:" -ForegroundColor White
            foreach ($prop in $data.stages.PSObject.Properties) {
                Write-Host "    - $($prop.Name): $($prop.Value.status)" -ForegroundColor DarkCyan
            }
        } else {
            Write-Host $_ -ForegroundColor DarkGray
        }
    }
    Write-Host ""
    exit 0
}

# Default: Display status
& $pyExe -c "
import json
from services.scheduler.engine import local_scheduler
print('STATUS:' + json.dumps(local_scheduler.get_status()))
" | ForEach-Object {
    if ($_ -like "STATUS:*") {
        $st = $_.Substring(7) | ConvertFrom-Json
        Write-Host "Timezone : $($st.timezone)" -ForegroundColor White
        Write-Host "Paused   : $($st.scheduler_paused)" -ForegroundColor $(if ($st.scheduler_paused) { "Yellow" } else { "Green" })
        Write-Host "Busy     : $($st.is_busy)" -ForegroundColor White
        Write-Host ""
        Write-Host "Configured Jobs:" -ForegroundColor Yellow
        foreach ($prop in $st.jobs.PSObject.Properties) {
            $j = $prop.Value
            Write-Host "  * $($j.name) ($($prop.Name))" -ForegroundColor Cyan
            Write-Host "      Schedule: $($j.schedule) | Status: $($j.status) | Retries: $($j.retry_count)" -ForegroundColor DarkGray
        }
    }
}
Write-Host ""
