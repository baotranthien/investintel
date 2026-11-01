# scripts/local/stop-investintel.ps1
# InvestIntel Local Services Graceful Teardown
[CmdletBinding()]
param(
    [switch]$StopOllama = $true,
    [switch]$Force
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$RunDir = Join-Path $ProjectRoot ".run"
$LogDir = Join-Path $ProjectRoot "logs\supervisor"
$SupervisorLog = Join-Path $LogDir "supervisor.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

function Log-Message {
    param([string]$Msg)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $entry = "[$ts] [STOP] $Msg"
    Write-Host $entry -ForegroundColor Cyan
    Add-Content -Path $SupervisorLog -Value $entry -ErrorAction SilentlyContinue
}

function Stop-SpecificProcess {
    param(
        [string]$ServiceName,
        [string]$PidFileName,
        [int]$Port,
        [string]$ExpectedProcName = ""
    )

    $pidFile = Join-Path $RunDir $PidFileName
    $targetPid = $null

    if (Test-Path $pidFile) {
        $rawPid = (Get-Content $pidFile -ErrorAction SilentlyContinue).Trim()
        if ($rawPid -match '^\d+$') {
            $targetPid = [int]$rawPid
        }
    }

    # If no PID file or process not running, check listening port
    if (-not $targetPid -and $Port -gt 0) {
        $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1
        if ($conn) {
            $targetPid = $conn.OwningProcess
        }
    }

    if (-not $targetPid) {
        Log-Message "$ServiceName is not running (Port $Port is free)."
        if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
        return $true
    }

    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if (-not $proc) {
        Log-Message "$ServiceName process $targetPid already exited."
        if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
        return $true
    }

    # Verify process identity
    $procName = $proc.ProcessName.ToLower()
    if ($ExpectedProcName -and ($procName -notlike "*$($ExpectedProcName.ToLower())*")) {
        Log-Message "WARNING: Process $targetPid on port $Port is '$procName', not matching expected '$ExpectedProcName'. Skipping for safety."
        return $false
    }

    Log-Message "Stopping $ServiceName (PID: $targetPid, Process: $($proc.ProcessName))..."

    # Try soft stop
    try {
        $proc.CloseMainWindow() | Out-Null
    } catch {}

    Start-Sleep -Milliseconds 800

    # If still running, terminate process tree
    if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {
        try {
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        } catch {}
    }

    # Wait up to 3 seconds for port to clear
    $stopped = $false
    for ($i = 0; $i -lt 6; $i++) {
        Start-Sleep -Milliseconds 500
        $conn = if ($Port -gt 0) { Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue } else { $null }
        $procLeft = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
        if (-not $conn -and -not $procLeft) {
            $stopped = $true
            break
        }
    }

    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }

    if ($stopped) {
        Log-Message "$ServiceName stopped successfully."
        return $true
    } else {
        Log-Message "WARNING: $ServiceName process $targetPid may still be lingering."
        return $false
    }
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Red
Write-Host "                INVESTINTEL LOCAL SERVICE TEARDOWN                 " -ForegroundColor Red
Write-Host "===================================================================" -ForegroundColor Red

# 1. Stop Next.js Frontend
Stop-SpecificProcess -ServiceName "Next.js Web UI" -PidFileName "frontend.pid" -Port 3000 -ExpectedProcName "node"

# 2. Stop Background Worker
Stop-SpecificProcess -ServiceName "Background Worker" -PidFileName "worker.pid" -Port 0 -ExpectedProcName "python"

# 3. Stop FastAPI Backend
Stop-SpecificProcess -ServiceName "FastAPI Backend" -PidFileName "backend.pid" -Port 8000 -ExpectedProcName "python"

# 4. Stop Ollama LLM (if requested)
if ($StopOllama) {
    Stop-SpecificProcess -ServiceName "Ollama LLM" -PidFileName "ollama.pid" -Port 11434 -ExpectedProcName "ollama"
} else {
    Log-Message "Leaving Ollama LLM running as requested."
}

Write-Host ""
Write-Host "Teardown complete. Verifying ports..." -ForegroundColor DarkGray
& (Join-Path $PSScriptRoot "status-investintel.ps1")

