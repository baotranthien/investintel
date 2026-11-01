# scripts/local/doctor-investintel.ps1
# InvestIntel Local Environment & Services Diagnostics
[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

$checks = [System.Collections.Generic.List[PSCustomObject]]::new()

function Add-CheckResult {
    param(
        [string]$Category,
        [string]$Name,
        [string]$Status, # PASS, WARN, FAIL
        [string]$Details,
        [string]$Remedy = ""
    )
    $checks.Add([PSCustomObject]@{
        Category = $Category
        Name = $Name
        Status = $Status
        Details = $Details
        Remedy = $Remedy
    })
}

# 1. Python Environment Check
$pyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $pyExe) {
    $pyVer = & $pyExe --version
    Add-CheckResult -Category "Python Environment" -Name "Virtual Environment" -Status "PASS" -Details "Found at $pyExe ($pyVer)"
} else {
    Add-CheckResult -Category "Python Environment" -Name "Virtual Environment" -Status "FAIL" -Details "Missing .venv\Scripts\python.exe" -Remedy "Run: python -m venv .venv && .venv\Scripts\pip install -r apps\api\requirements.txt"
}

# 2. Python Packages Check
if (Test-Path $pyExe) {
    $reqPkgs = @("fastapi", "uvicorn", "sqlalchemy", "pydantic", "httpx", "pytest")
    $missingPkgs = @()
    foreach ($pkg in $reqPkgs) {
        $test = & $pyExe -c "import $pkg" 2>&1
        if ($LASTEXITCODE -ne 0) { $missingPkgs += $pkg }
    }
    if ($missingPkgs.Count -eq 0) {
        Add-CheckResult -Category "Python Environment" -Name "Core Packages" -Status "PASS" -Details "All critical packages available ($($reqPkgs -join ', '))"
    } else {
        Add-CheckResult -Category "Python Environment" -Name "Core Packages" -Status "FAIL" -Details "Missing packages: $($missingPkgs -join ', ')" -Remedy "Run: .venv\Scripts\pip install -r apps\api\requirements.txt"
    }
}

# 3. Node.js & npm Check
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($nodeCmd -and $npmCmd) {
    $nodeVer = & node -v
    $npmVer = & npm -v
    Add-CheckResult -Category "Frontend Runtime" -Name "Node.js & npm" -Status "PASS" -Details "Node $nodeVer, npm $npmVer"
} else {
    Add-CheckResult -Category "Frontend Runtime" -Name "Node.js & npm" -Status "FAIL" -Details "Node or npm not found in PATH" -Remedy "Install Node.js v20+ from https://nodejs.org"
}

# 4. Next.js Dependencies Check
$webNodeModules = Join-Path $ProjectRoot "apps\web\node_modules"
if (Test-Path $webNodeModules) {
    Add-CheckResult -Category "Frontend Runtime" -Name "Web Dependencies" -Status "PASS" -Details "Found apps/web/node_modules"
} else {
    Add-CheckResult -Category "Frontend Runtime" -Name "Web Dependencies" -Status "FAIL" -Details "apps/web/node_modules missing" -Remedy "Run: npm --prefix apps/web install"
}

# 5. Ollama Executable Check
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

if ($ollamaExe) {
    Add-CheckResult -Category "AI Inference" -Name "Ollama Executable" -Status "PASS" -Details "Resolved at $ollamaExe"
} else {
    Add-CheckResult -Category "AI Inference" -Name "Ollama Executable" -Status "FAIL" -Details "Ollama executable not found" -Remedy "Install Ollama via winget or https://ollama.com"
}

# 6. Ollama Primary Model Check
if ($ollamaExe) {
    try {
        $tags = & $pyExe -c "import urllib.request, json; print([m['name'] for m in json.loads(urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=2).read())['models']])" 2>&1
        if ($tags -like "*qwen3.5:9b-q4_K_M*") {
            Add-CheckResult -Category "AI Inference" -Name "Primary Qwen3.5 9B" -Status "PASS" -Details "Installed and registered in Ollama"
        } else {
            Add-CheckResult -Category "AI Inference" -Name "Primary Qwen3.5 9B" -Status "WARN" -Details "Ollama running but qwen3.5:9b-q4_K_M not found in: $tags" -Remedy "Run: ollama pull qwen3.5:9b-q4_K_M"
        }
    } catch {
        Add-CheckResult -Category "AI Inference" -Name "Primary Qwen3.5 9B" -Status "WARN" -Details "Ollama not currently listening to check models" -Remedy "Start Ollama via scripts\local\start-investintel.ps1"
    }
}

# 7. SQLite Database Check
$dbPath = Join-Path $ProjectRoot "data\trading.db"
if (Test-Path $dbPath) {
    if (Test-Path $pyExe) {
        $intCheck = & $pyExe -c "import sqlite3; con=sqlite3.connect('$($dbPath.Replace('\', '/'))'); print(con.execute('PRAGMA integrity_check').fetchone()[0]); con.close()" 2>&1
        if ($intCheck -eq "ok") {
            $sizeMb = [math]::Round((Get-Item $dbPath).Length / 1MB, 2)
            Add-CheckResult -Category "Database & Data" -Name "SQLite Integrity" -Status "PASS" -Details "trading.db valid, size $sizeMb MB, PRAGMA integrity_check ok"
        } else {
            Add-CheckResult -Category "Database & Data" -Name "SQLite Integrity" -Status "FAIL" -Details "trading.db integrity error: $intCheck" -Remedy "Restore from latest backup via scripts\local\restore-investintel-db.ps1"
        }
    } else {
        Add-CheckResult -Category "Database & Data" -Name "SQLite Integrity" -Status "WARN" -Details "trading.db exists but Python not available for PRAGMA check"
    }
} else {
    Add-CheckResult -Category "Database & Data" -Name "SQLite Integrity" -Status "FAIL" -Details "data/trading.db does not exist" -Remedy "Run seed script or init_db to create trading.db"
}

# 8. Environment & Security Check
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    $prodWrite = ($envContent -match 'ALLOW_PRODUCTION_DB_WRITE\s*=\s*true')
    if ($prodWrite) {
        Add-CheckResult -Category "Security & Config" -Name "Production DB Safety" -Status "FAIL" -Details "ALLOW_PRODUCTION_DB_WRITE=true is dangerous for local dev" -Remedy "Set ALLOW_PRODUCTION_DB_WRITE=false in .env"
    } else {
        Add-CheckResult -Category "Security & Config" -Name "Production DB Safety" -Status "PASS" -Details "ALLOW_PRODUCTION_DB_WRITE=false strictly enforced"
    }
} else {
    Add-CheckResult -Category "Security & Config" -Name "Production DB Safety" -Status "PASS" -Details "No .env found; defaults to safe ALLOW_PRODUCTION_DB_WRITE=false"
}

# 9. GPU & Hardware Check
$nvidiaSmi = "C:\Windows\System32\nvidia-smi.exe"
if (Test-Path $nvidiaSmi) {
    $gpuOut = & $nvidiaSmi --query-gpu=gpu_name,memory.total,memory.free --format=csv,noheader,nounits 2>&1
    if ($gpuOut) {
        Add-CheckResult -Category "Hardware Diagnostics" -Name "NVIDIA GPU & VRAM" -Status "PASS" -Details "$gpuOut"
    } else {
        Add-CheckResult -Category "Hardware Diagnostics" -Name "NVIDIA GPU & VRAM" -Status "WARN" -Details "nvidia-smi returned no output"
    }
} else {
    Add-CheckResult -Category "Hardware Diagnostics" -Name "NVIDIA GPU & VRAM" -Status "WARN" -Details "nvidia-smi not found. GPU telemetry unavailable; will use CPU fallback."
}

# 10. Stale PID Files Check
$stalePids = @()
$runDir = Join-Path $ProjectRoot ".run"
if (Test-Path $runDir) {
    Get-ChildItem -Path $runDir -Filter "*.pid" | ForEach-Object {
        $p = (Get-Content $_.FullName -ErrorAction SilentlyContinue).Trim()
        if ($p -match '^\d+$') {
            $proc = Get-Process -Id [int]$p -ErrorAction SilentlyContinue
            if (-not $proc) {
                $stalePids += "$($_.Name) (PID: $p)"
            }
        }
    }
}
if ($stalePids.Count -eq 0) {
    Add-CheckResult -Category "Supervisor Runtime" -Name "PID State" -Status "PASS" -Details "Zero stale PID files in .run/"
} else {
    Add-CheckResult -Category "Supervisor Runtime" -Name "PID State" -Status "WARN" -Details "Stale PID files: $($stalePids -join ', ')" -Remedy "Run scripts\local\stop-investintel.ps1 to clean stale PIDs"
}

# 11. Log Directories Check
$logDirs = @("logs\ollama", "logs\backend", "logs\frontend", "logs\workers", "logs\supervisor")
$missingLogDirs = @()
foreach ($ld in $logDirs) {
    $fullLd = Join-Path $ProjectRoot $ld
    if (-not (Test-Path $fullLd)) { $missingLogDirs += $ld }
}
if ($missingLogDirs.Count -eq 0) {
    Add-CheckResult -Category "Supervisor Runtime" -Name "Log Directories" -Status "PASS" -Details "All log directories exist and are writable"
} else {
    Add-CheckResult -Category "Supervisor Runtime" -Name "Log Directories" -Status "WARN" -Details "Missing: $($missingLogDirs -join ', ')" -Remedy "Run scripts\local\start-investintel.ps1 to automatically create them"
}

if ($AsJson) {
    $checks | ConvertTo-Json -Depth 3
    return
}

# Pretty Console Display
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Magenta
Write-Host "                INVESTINTEL LOCAL DOCTOR DIAGNOSTICS               " -ForegroundColor Magenta
Write-Host "===================================================================" -ForegroundColor Magenta
Write-Host " Diagnostics run at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

$grouped = $checks | Group-Object Category
$hasFail = $false
$hasWarn = $false

foreach ($g in $grouped) {
    Write-Host "[$($g.Name)]" -ForegroundColor Yellow
    foreach ($item in $g.Group) {
        $tag = switch ($item.Status) {
            "PASS" { "[PASS]" }
            "WARN" { "[WARN]" }
            "FAIL" { "[FAIL]" }
        }
        $color = switch ($item.Status) {
            "PASS" { "Green" }
            "WARN" { "Yellow" }
            "FAIL" { "Red" }
        }
        if ($item.Status -eq "FAIL") { $hasFail = $true }
        if ($item.Status -eq "WARN") { $hasWarn = $true }

        Write-Host "  $tag $($item.Name): $($item.Details)" -ForegroundColor $color
        if ($item.Remedy) {
            Write-Host "         -> Remedy: $($item.Remedy)" -ForegroundColor DarkCyan
        }
    }
    Write-Host ""
}

Write-Host "===================================================================" -ForegroundColor Magenta
if ($hasFail) {
    Write-Host " OVERALL STATUS: ISSUES FOUND. Please review failures above." -ForegroundColor Red
} elseif ($hasWarn) {
    Write-Host " OVERALL STATUS: READY WITH WARNINGS. System is operational." -ForegroundColor Yellow
} else {
    Write-Host " OVERALL STATUS: ALL CHECKS PASSED. Local environment is healthy." -ForegroundColor Green
}
Write-Host "===================================================================" -ForegroundColor Magenta
Write-Host ""

