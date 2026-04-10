# Stop EVERY process listening on port 8000, then start this repo's API once (run_api:app).

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "run_api.py"))) {
    Write-Error "Run dev-up.ps1 from the repo root (same folder as run_api.py)."
    exit 1
}

function Get-PidsOnPort8000 {
    $pids = @{}
    foreach ($row in (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        $pids[[int]$row.OwningProcess] = $true
    }
    # netstat backup — PID is last column on LISTENING lines
    foreach ($line in (netstat -ano 2>$null)) {
        if ($line -notmatch "LISTENING") { continue }
        if ($line -notmatch ":8000") { continue }
        if ($line -match "\s(\d+)\s*$") {
            $pids[[int]$Matches[1]] = $true
        }
    }
    return @($pids.Keys)
}

Write-Host "=== Stopping all listeners on port 8000 ===" -ForegroundColor Yellow
for ($round = 1; $round -le 12; $round++) {
    $pids = Get-PidsOnPort8000
    if ($pids.Count -eq 0) {
        Write-Host "Port 8000 is free (round $round)." -ForegroundColor Green
        break
    }
    Write-Host "Round $round — PIDs: $($pids -join ', ')"
    foreach ($procId in $pids) {
        if ($procId -lt 4) { continue }
        $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        $cmd = if ($p) { $p.CommandLine } else { "(unknown)" }
        Write-Host "  taskkill /T /F /PID $procId"
        Write-Host "    $cmd"
        & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    }
    Start-Sleep -Milliseconds 800
}

Start-Sleep -Seconds 1
$still = Get-PidsOnPort8000
if ($still.Count -gt 0) {
    Write-Host ""
    Write-Warning "Port 8000 still held by PID(s): $($still -join ', '). Run Task Manager as admin or reboot, then try again."
    netstat -ano | findstr ":8000"
    exit 1
}

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Missing $py — create the venv first."
    exit 1
}

Set-Location $Root
$env:PYTHONPATH = $Root
Write-Host ""
Write-Host "=== Starting API ===" -ForegroundColor Cyan
Write-Host "PYTHONPATH=$Root"
Write-Host "URL:  http://127.0.0.1:8000"
Write-Host "Test: http://127.0.0.1:8000/health  (expect code_revision + index_size 9)"
Write-Host "Web:  cd web ; npm run dev"
Write-Host ""
& $py -m uvicorn run_api:app --reload --host 127.0.0.1 --port 8000
