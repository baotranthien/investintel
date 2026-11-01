# scripts/local/start-investintel.ps1
# InvestIntel Local Services Unified Startup Orchestrator
[CmdletBinding()]
param(
    [switch]$WarmUpLLM,
    [switch]$SkipFrontend,
    [switch]$SkipLLM
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

$RunDir = Join-Path $ProjectRoot ".run"
$LogDir = Join-Path $ProjectRoot "logs\supervisor"
$SupervisorLog = Join-Path $LogDir "supervisor.log"

# Ensure directories exist
@($RunDir, $LogDir, (Join-Path $ProjectRoot "logs\ollama"), (Join-Path $ProjectRoot "logs\backend"), (Join-Path $ProjectRoot "logs\frontend"), (Join-Path $ProjectRoot "logs\workers")) | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
}

function Log-Message {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $entry = "[$ts] [$Level] $Msg"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "OK"    { "Green" }
        default { "Cyan" }
    }
    Write-Host $entry -ForegroundColor $color
    Add-Content -Path $SupervisorLog -Value $entry -ErrorAction SilentlyContinue

    # Rotate supervisor log if > 10MB
    if ((Test-Path $SupervisorLog) -and (Get-Item $SupervisorLog).Length -gt 10MB) {
        $archive = Join-Path $LogDir "supervisor_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
        Move-Item -Path $SupervisorLog -Destination $archive -Force -ErrorAction SilentlyContinue
    }
}

function Rotate-LogFile {
    param([string]$FilePath)
    if ((Test-Path $FilePath) -and (Get-Item $FilePath).Length -gt 10MB) {
        $dir = Split-Path $FilePath
        $base = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
        $ext = [System.IO.Path]::GetExtension($FilePath)
        $archive = Join-Path $dir "${base}_$(Get-Date -Format 'yyyyMMdd_HHmmss')${ext}"
        Move-Item -Path $FilePath -Destination $archive -Force -ErrorAction SilentlyContinue
    }
}

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

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "               INVESTINTEL LOCAL SERVICE ORCHESTRATOR              " -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Log-Message "Starting InvestIntel service supervisor..." "INFO"

# Preflight: Verify root environment
$pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    Log-Message "CRITICAL: Python virtual environment not found at $pyExe" "ERROR"
    exit 1
}

# Resolve Ollama executable
$ollamaExe = $null
$possibleOllama = @(
    "C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe",
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
)
foreach ($p in $possibleOllama) {
    if (Test-Path $p) { $ollamaExe = $p; break }
}
if (-not $ollamaExe) {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { $ollamaExe = $cmd.Source }
}

# -------------------------------------------------------------
# STEP 1: OLLAMA LLM SERVICE
# -------------------------------------------------------------
if (-not $SkipLLM) {
    Log-Message "Step 1/3: Checking Ollama LLM Service..." "INFO"
    $ollamaHealth = Test-HttpEndpoint -Url "http://127.0.0.1:11434/api/tags"

    if ($ollamaHealth.Success) {
        Log-Message "Ollama is already running and healthy on port 11434." "OK"
    } else {
        if (-not $ollamaExe) {
            Log-Message "ERROR: Ollama executable not found. Please install Ollama." "ERROR"
            exit 1
        }
        Log-Message "Starting Ollama daemon ($ollamaExe serve)..." "INFO"
        $ollamaLog = Join-Path $ProjectRoot "logs\ollama\ollama.log"
        Rotate-LogFile -FilePath $ollamaLog

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $ollamaExe
        $psi.Arguments = "serve"
        $psi.WorkingDirectory = $ProjectRoot
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true

        $proc = [System.Diagnostics.Process]::Start($psi)
        if ($proc) {
            Set-Content -Path (Join-Path $RunDir "ollama.pid") -Value $proc.Id
            Log-Message "Ollama process launched with PID $($proc.Id). Waiting for HTTP health..." "INFO"

            # Wait for health up to 15 seconds
            $ready = $false
            for ($i = 0; $i -lt 15; $i++) {
                Start-Sleep -Seconds 1
                $check = Test-HttpEndpoint -Url "http://127.0.0.1:11434/api/tags"
                if ($check.Success) {
                    $ready = $true
                    break
                }
            }
            if ($ready) {
                Log-Message "Ollama is healthy on http://127.0.0.1:11434." "OK"
            } else {
                Log-Message "WARNING: Ollama process started (PID $($proc.Id)) but health check timed out." "WARN"
            }
        } else {
            Log-Message "ERROR: Failed to launch Ollama process." "ERROR"
            exit 1
        }
    }

    # Verify primary model
    $tagsCheck = Test-HttpEndpoint -Url "http://127.0.0.1:11434/api/tags"
    if ($tagsCheck.Success -and $tagsCheck.Body) {
        if ($tagsCheck.Body -notlike "*qwen3.5:9b-q4_K_M*") {
            Log-Message "WARNING: Primary model 'qwen3.5:9b-q4_K_M' not found in Ollama models list." "WARN"
        } else {
            Log-Message "Verified primary model 'qwen3.5:9b-q4_K_M' is available." "OK"
        }
    }

    # Warm up LLM into VRAM if requested
    if ($WarmUpLLM) {
        Log-Message "Warming up Qwen3.5 9B into GPU VRAM..." "INFO"
        & $pyExe -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=json.dumps({'model': 'qwen3.5:9b-q4_K_M', 'prompt': 'ping', 'stream': False}).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req, timeout=30)
    print('VRAM Warm-up successful.')
except Exception as e:
    print('VRAM Warm-up exception:', e)
"
    }
}

# -------------------------------------------------------------
# STEP 2: FASTAPI BACKEND SERVICE
# -------------------------------------------------------------
Log-Message "Step 2/3: Checking FastAPI Backend Service..." "INFO"
$apiHealth = Test-HttpEndpoint -Url "http://127.0.0.1:8000/health"

if ($apiHealth.Success) {
    Log-Message "FastAPI Backend is already running and healthy on port 8000." "OK"
} else {
    Log-Message "Starting FastAPI Uvicorn server on port 8000..." "INFO"
    $backendLog = Join-Path $ProjectRoot "logs\backend\backend.log"
    Rotate-LogFile -FilePath $backendLog

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pyExe
    $psi.Arguments = "-m uvicorn apps.api.main:app --port 8000 --host 127.0.0.1"
    $psi.WorkingDirectory = $ProjectRoot
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    if ($proc) {
        Set-Content -Path (Join-Path $RunDir "backend.pid") -Value $proc.Id
        Log-Message "FastAPI launched with PID $($proc.Id). Waiting for HTTP health..." "INFO"

        # Wait up to 15 seconds
        $ready = $false
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 1
            $check = Test-HttpEndpoint -Url "http://127.0.0.1:8000/health"
            if ($check.Success) {
                $ready = $true
                break
            }
        }
        if ($ready) {
            Log-Message "FastAPI Backend is healthy on http://127.0.0.1:8000." "OK"
        } else {
            Log-Message "WARNING: FastAPI process started (PID $($proc.Id)) but health check timed out." "WARN"
        }
    } else {
        Log-Message "ERROR: Failed to launch FastAPI process." "ERROR"
        exit 1
    }
}

# -------------------------------------------------------------
# STEP 3: NEXT.JS FRONTEND SERVICE
# -------------------------------------------------------------
if (-not $SkipFrontend) {
    Log-Message "Step 3/3: Checking Next.js Frontend Service..." "INFO"
    $webHealth = Test-HttpEndpoint -Url "http://localhost:3000/ai"

    if ($webHealth.Success -or $webHealth.StatusCode -eq 200 -or $webHealth.StatusCode -eq 307) {
        Log-Message "Next.js Frontend is already running and healthy on port 3000." "OK"
    } else {
        Log-Message "Starting Next.js Turbopack dev server on port 3000..." "INFO"
        $frontendLog = Join-Path $ProjectRoot "logs\frontend\frontend.log"
        Rotate-LogFile -FilePath $frontendLog

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "cmd.exe"
        $psi.Arguments = "/c npm --prefix apps/web run dev"
        $psi.WorkingDirectory = $ProjectRoot
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true

        $proc = [System.Diagnostics.Process]::Start($psi)
        if ($proc) {
            Set-Content -Path (Join-Path $RunDir "frontend.pid") -Value $proc.Id
            Log-Message "Next.js launched with PID $($proc.Id). Waiting for readiness..." "INFO"

            # Wait up to 25 seconds
            $ready = $false
            for ($i = 0; $i -lt 25; $i++) {
                Start-Sleep -Seconds 1
                $check = Test-HttpEndpoint -Url "http://localhost:3000"
                if ($check.Success -or $check.StatusCode -eq 200 -or $check.StatusCode -eq 307) {
                    $ready = $true
                    break
                }
            }
            if ($ready) {
                Log-Message "Next.js Frontend is ready on http://localhost:3000." "OK"
            } else {
                Log-Message "WARNING: Next.js process started (PID $($proc.Id)) but readiness check timed out." "WARN"
            }
        } else {
            Log-Message "ERROR: Failed to launch Next.js frontend." "ERROR"
        }
    }
}

Log-Message "InvestIntel service stack startup sequence complete." "OK"
& (Join-Path $PSScriptRoot "status-investintel.ps1")

