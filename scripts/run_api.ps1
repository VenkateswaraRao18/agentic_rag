# Stop every process listening on port 8000, then start a single API server from the repo root.
# Use this if /health looks stale (no code_revision) or index_size stays wrong — multiple uvicorn
# instances often bind 0.0.0.0 vs 127.0.0.1 and curl can hit the wrong one.

$ErrorActionPreference = "Stop"
# This file lives in <repo>/scripts — repo root is one level up.
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app\main.py"))) {
    Write-Error "Expected app\main.py under $Root"
    exit 1
}
Set-Location $Root

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($c in $listeners) {
    $procId = $c.OwningProcess
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId"
        Write-Host "Stopping PID $procId : $($proc.CommandLine)"
        Stop-Process -Id $procId -Force -ErrorAction Stop
    } catch {
        Write-Warning "Could not stop PID ${procId}: $_"
    }
}
Start-Sleep -Seconds 1

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Missing $py — create the venv first."
    exit 1
}

Write-Host "Starting API from $Root ..."
# Use run_api:app (repo root) so `app` always loads from this project, not another `app` on PYTHONPATH.
Set-Location $Root
& $py -m uvicorn run_api:app --reload --host 127.0.0.1 --port 8000
