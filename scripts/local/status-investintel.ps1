# scripts/local/status-investintel.ps1
# InvestIntel Local Services Status Inspection
[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Test-HttpEndpoint {
    param([string]$Url, [int]$TimeoutSec = 2)
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Timeout = $TimeoutSec * 1000
        $req.Method = "GET"
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $body = $reader.ReadToEnd()
        $resp.Close()
        return @{ Success = ($code -ge 200 -and $code -lt 400); StatusCode = $code; Body = $body }
    } catch [System.Net.WebException] {
        if ($_.Response) {
            $code = [int]$_.Response.StatusCode
            $reader = New-Object System.IO.StreamReader($_.Response.GetResponseStream())
            $body = $reader.ReadToEnd()
            $_.Response.Close()
            return @{ Success = ($code -ge 200 -and $code -lt 400); StatusCode = $code; Body = $body }
        }
        return @{ Success = $false; StatusCode = 0; Error = $_.Message }
    } catch {
        return @{ Success = $false; StatusCode = 0; Error = $_.Message }
    }
}

function Get-PortProcess {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        return @{
            PID = $conn.OwningProcess
            Name = if ($proc) { $proc.ProcessName } else { "Unknown" }
            Path = if ($proc) { $proc.Path } else { "" }
        }
    }
    return $null
}

# 1. Ollama Inspection
$ollamaPort = 11434
$ollamaProc = Get-PortProcess -Port $ollamaPort
$ollamaHealth = Test-HttpEndpoint -Url "http://127.0.0.1:$ollamaPort/api/tags"
$ollamaModels = @()
$primaryModelInstalled = $false
if ($ollamaHealth.Success -and $ollamaHealth.Body) {
    try {
        $json = $ollamaHealth.Body | ConvertFrom-Json
        if ($json.models) {
            $ollamaModels = $json.models | ForEach-Object { $_.name }
            $primaryModelInstalled = ($ollamaModels -contains "qwen3.5:9b-q4_K_M")
        }
    } catch {}
}

$ollamaStatus = if ($ollamaHealth.Success) {
    if ($primaryModelInstalled) { "RUNNING (Healthy)" } else { "RUNNING (Missing Qwen3.5 9B)" }
} elseif ($ollamaProc) {
    "RUNNING (Unhealthy)"
} else {
    "STOPPED"
}

# 2. FastAPI Backend Inspection
$apiPort = 8000
$apiProc = Get-PortProcess -Port $apiPort
$apiHealth = Test-HttpEndpoint -Url "http://127.0.0.1:$apiPort/health"
$apiStatus = if ($apiHealth.Success) {
    "RUNNING (Healthy)"
} elseif ($apiProc) {
    "RUNNING (Unhealthy)"
} else {
    "STOPPED"
}

# 3. Next.js Frontend Inspection
$webPort = 3000
$webProc = Get-PortProcess -Port $webPort
$webHealth = Test-HttpEndpoint -Url "http://localhost:$webPort/ai"
$webStatus = if ($webHealth.Success -or $webHealth.StatusCode -eq 200 -or $webHealth.StatusCode -eq 307) {
    "RUNNING (Healthy)"
} elseif ($webProc) {
    "RUNNING (Unhealthy)"
} else {
    "STOPPED"
}

# 4. SQLite Database Inspection
$dbPath = Join-Path $ProjectRoot "data\trading.db"
$dbStatus = "UNKNOWN"
$dbSize = 0
$dbIntegrity = "NOT CHECKED"
if (Test-Path $dbPath) {
    $dbFile = Get-Item $dbPath
    $dbSize = [math]::Round($dbFile.Length / 1MB, 2)
    $pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $pyExe) {
        $intCheck = & $pyExe -c "import sqlite3; con=sqlite3.connect('$($dbPath.Replace('\', '/'))'); print(con.execute('PRAGMA integrity_check').fetchone()[0]); con.close()"
        if ($intCheck -eq "ok") {
            $dbIntegrity = "PASS (ok)"
            $dbStatus = "HEALTHY"
        } else {
            $dbIntegrity = "CORRUPTED ($intCheck)"
            $dbStatus = "DEGRADED"
        }
    } else {
        $dbStatus = "ACCESSIBLE"
        $dbIntegrity = "Python not found for PRAGMA"
    }
} else {
    $dbStatus = "MISSING"
}

# 5. GPU & Hardware Telemetry
$gpuName = "UNKNOWN"
$vramTotal = 0
$vramUsed = 0
$vramFree = 0
$nvidiaSmi = "C:\Windows\System32\nvidia-smi.exe"
if (Test-Path $nvidiaSmi) {
    try {
        $gpuOut = & $nvidiaSmi --query-gpu=gpu_name,memory.total,memory.used,memory.free --format=csv,noheader,nounits
        if ($gpuOut) {
            $parts = $gpuOut.Split(",")
            if ($parts.Count -ge 4) {
                $gpuName = $parts[0].Trim()
                $vramTotal = [int]$parts[1].Trim()
                $vramUsed = [int]$parts[2].Trim()
                $vramFree = [int]$parts[3].Trim()
            }
        }
    } catch {}
}

# 6. Background Worker / Scheduler Inspection
$workerPidFile = Join-Path $ProjectRoot ".run\worker.pid"
$workerStatus = "STOPPED"
$workerPid = $null
if (Test-Path $workerPidFile) {
    $wPid = (Get-Content $workerPidFile -ErrorAction SilentlyContinue).Trim()
    if ($wPid) {
        $wProc = Get-Process -Id $wPid -ErrorAction SilentlyContinue
        if ($wProc) {
            $workerStatus = "RUNNING (PID: $wPid)"
            $workerPid = $wPid
        } else {
            $workerStatus = "STALE PID ($wPid)"
        }
    }
}

$statusResult = [PSCustomObject]@{
    Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Ollama = [PSCustomObject]@{
        Status = $ollamaStatus
        Port = $ollamaPort
        PID = if ($ollamaProc) { $ollamaProc.PID } else { $null }
        PrimaryModelInstalled = $primaryModelInstalled
        Models = $ollamaModels
    }
    FastAPI = [PSCustomObject]@{
        Status = $apiStatus
        Port = $apiPort
        PID = if ($apiProc) { $apiProc.PID } else { $null }
        HealthUrl = "http://127.0.0.1:$apiPort/health"
    }
    NextJs = [PSCustomObject]@{
        Status = $webStatus
        Port = $webPort
        PID = if ($webProc) { $webProc.PID } else { $null }
        Url = "http://localhost:$webPort"
    }
    SQLite = [PSCustomObject]@{
        Status = $dbStatus
        Path = $dbPath
        SizeBytes = if (Test-Path $dbPath) { (Get-Item $dbPath).Length } else { 0 }
        SizeMB = $dbSize
        Integrity = $dbIntegrity
    }
    GPU = [PSCustomObject]@{
        Name = $gpuName
        VramTotalMB = $vramTotal
        VramUsedMB = $vramUsed
        VramFreeMB = $vramFree
    }
    Worker = [PSCustomObject]@{
        Status = $workerStatus
        PID = $workerPid
    }
}

if ($AsJson) {
    $statusResult | ConvertTo-Json -Depth 5
    return
}

# Pretty Console Display
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "                INVESTINTEL LOCAL SERVICE STATUS                   " -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host " Checked at: $($statusResult.Timestamp)" -ForegroundColor DarkGray
Write-Host ""

$format = "{0,-16} | {1,-24} | {2,-8} | {3,-12}"
Write-Host ([string]::Format($format, "SERVICE", "STATUS", "PORT", "PID/DETAILS")) -ForegroundColor Yellow
Write-Host ("-" * 67) -ForegroundColor DarkGray

$oColor = if ($ollamaStatus -like "RUNNING*Healthy*") { "Green" } elseif ($ollamaStatus -like "RUNNING*") { "Yellow" } else { "Red" }
Write-Host ([string]::Format($format, "Ollama LLM", $ollamaStatus, $ollamaPort, $(if ($ollamaProc) { $ollamaProc.PID } else { "-" }))) -ForegroundColor $oColor

$aColor = if ($apiStatus -like "*Healthy*") { "Green" } elseif ($apiStatus -like "RUNNING*") { "Yellow" } else { "Red" }
Write-Host ([string]::Format($format, "FastAPI API", $apiStatus, $apiPort, $(if ($apiProc) { $apiProc.PID } else { "-" }))) -ForegroundColor $aColor

$wColor = if ($webStatus -like "*Healthy*") { "Green" } elseif ($webStatus -like "RUNNING*") { "Yellow" } else { "Red" }
Write-Host ([string]::Format($format, "Next.js Web", $webStatus, $webPort, $(if ($webProc) { $webProc.PID } else { "-" }))) -ForegroundColor $wColor

$dColor = if ($dbStatus -eq "HEALTHY") { "Green" } else { "Yellow" }
Write-Host ([string]::Format($format, "SQLite DB", "$dbStatus ($dbIntegrity)", "FILE", "$dbSize MB")) -ForegroundColor $dColor

$kColor = if ($workerStatus -like "RUNNING*") { "Green" } else { "DarkGray" }
Write-Host ([string]::Format($format, "Worker/Cron", $workerStatus, "-", $(if ($workerPid) { "PID: $workerPid" } else { "Idle/Standalone" }))) -ForegroundColor $kColor

Write-Host ("-" * 67) -ForegroundColor DarkGray
Write-Host ""
Write-Host "Hardware & Model Telemetry:" -ForegroundColor Cyan
Write-Host "  GPU Detected   : $gpuName" -ForegroundColor White
Write-Host "  VRAM (Used/Tot): $vramUsed MB / $vramTotal MB (Free: $vramFree MB)" -ForegroundColor White
Write-Host "  Primary Model  : qwen3.5:9b-q4_K_M (Installed: $(if ($primaryModelInstalled) { 'YES' } else { 'NO' }))" -ForegroundColor White
Write-Host "  Active Models  : $($ollamaModels -join ', ')" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Local Entry Points:" -ForegroundColor Cyan
Write-Host "  Web Dashboard  : http://localhost:3000" -ForegroundColor Yellow
Write-Host "  AI Analyst     : http://localhost:3000/ai" -ForegroundColor Yellow
Write-Host "  Stock Screener : http://localhost:3000/screener" -ForegroundColor Yellow
Write-Host "  Opportunities  : http://localhost:3000/opportunities" -ForegroundColor Yellow
Write-Host "  FastAPI Health : http://127.0.0.1:8000/health" -ForegroundColor Yellow
Write-Host "  Swagger Docs   : http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host ""

