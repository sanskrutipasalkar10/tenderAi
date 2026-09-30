<#
.SYNOPSIS
    Starts the full native (no-Docker) dev stack in separate, persistent windows:
    the S3-compatible mock (moto.server), the Celery worker, the FastAPI backend,
    and the Next.js frontend - then creates the S3 bucket the mock needs.

.WHY THIS EXISTS
    Every piece here has been a real, repeated source of friction on a fresh
    machine (see docs/DECISIONS.md #79/#84):
      - moto.server's data is in-memory only, so its bucket must be recreated
        every time that process restarts, and it's easy to accidentally kill it
        by reusing its terminal window for another command.
      - The Celery worker must be started with -Q default,llm specifically -
        the plain command (no -Q) only consumes "default" and silently never
        picks up ingest_document_task, which is queued to "llm". A document
        uploaded against a worker missing this flag sits at status="uploaded"
        forever with no error anywhere.
      - Four terminal windows are easy to lose track of by hand.
    This script does not replace understanding those steps (see README.md
    section 4) - it just removes the chance of getting the mechanics wrong.

.NOT COVERED HERE, ON PURPOSE
    - "alembic upgrade head" - a deliberate step you run yourself after a
      git pull that includes a new migration, not something to auto-apply
      silently every time you start working.
    - Postgres and Redis - this project's Postgres is the shared team instance
      (docs/DECISIONS.md #21), not something local to start; Redis is assumed
      already running as a local service. Both are checked (warn-only) below.

.USAGE
    Run from anywhere - paths are resolved relative to this script's own
    location, not your current directory:
        powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1
    Safe to re-run: already-running pieces are detected and skipped rather
    than duplicated (docs/DECISIONS.md #79 - this project has hit real,
    confusing bugs from two processes bound to the same port before).
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Test-CeleryRunning {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "celery.*worker" }
    return $null -ne $procs
}

function Start-InNewWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    Write-Host "  Starting: $Title" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$WorkingDirectory'; $Command"
    ) | Out-Null
}

Write-Host ""
Write-Host "=== Tender AI Platform - dev stack startup ===" -ForegroundColor Green
Write-Host ""

# --- Sanity checks -------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: backend\.venv not found at $VenvPython" -ForegroundColor Red
    Write-Host "Run: cd backend; python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "ERROR: frontend\node_modules not found - run 'npm install' in frontend\ first" -ForegroundColor Red
    exit 1
}

if (-not (Test-PortListening -Port 6379)) {
    Write-Host "WARNING: nothing listening on 6379 (Redis) - Celery and the backend need it." -ForegroundColor Yellow
    Write-Host "         This script doesn't start Redis; start it (or its Windows service) yourself."
    Write-Host ""
}

# --- moto.server (S3 mock) ------------------------------------------------
Write-Host "[1/4] S3 mock (moto.server)" -ForegroundColor Green
$motoWasRunning = Test-PortListening -Port 9000
if ($motoWasRunning) {
    Write-Host "  Already running on :9000 - leaving it alone (its bucket may already exist)."
} else {
    Start-InNewWindow -Title "moto.server (S3 mock)" -WorkingDirectory $BackendDir `
        -Command "& '$VenvPython' -m moto.server -p 9000"

    Write-Host "  Waiting for it to come up..." -NoNewline
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-PortListening -Port 9000) { $ready = $true; break }
        Write-Host "." -NoNewline
    }
    Write-Host ""
    if (-not $ready) {
        Write-Host "  ERROR: moto.server didn't come up within 15s - check its window for errors." -ForegroundColor Red
        exit 1
    }
}

# moto's data is in-memory only (see file header) - always (re)create the
# bucket, cheap and idempotent even if it already exists. `app.storage.objects`
# only resolves as a package with backend\ as the working directory.
Write-Host "  Ensuring the 'tenders' bucket exists..."
Push-Location $BackendDir
& $VenvPython -c "from app.storage.objects import ensure_bucket_exists; ensure_bucket_exists(); print('  Bucket OK.')"
Pop-Location

# --- Celery worker ---------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Celery worker" -ForegroundColor Green
if (Test-CeleryRunning) {
    Write-Host "  A celery worker process is already running - leaving it alone."
    Write-Host "  (If uploads still get stuck at 'uploaded', that worker may be missing" -ForegroundColor Yellow
    Write-Host "  -Q default,llm - stop it and re-run this script to get a correct one.)" -ForegroundColor Yellow
} else {
    Start-InNewWindow -Title "Celery worker" -WorkingDirectory $BackendDir `
        -Command "& '$VenvPython' -m celery -A app.workers.celery_app worker --pool=solo --loglevel=info -Q default,llm"
}

# --- Backend (uvicorn) ------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Backend (uvicorn)" -ForegroundColor Green
if (Test-PortListening -Port 8000) {
    Write-Host "  Already running on :8000 - leaving it alone."
} else {
    Start-InNewWindow -Title "Backend (uvicorn :8000)" -WorkingDirectory $BackendDir `
        -Command "& '$VenvPython' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
}

# --- Frontend (Next.js) -----------------------------------------------------
Write-Host ""
Write-Host "[4/4] Frontend (npm run dev)" -ForegroundColor Green
if (Test-PortListening -Port 3000) {
    Write-Host "  Already running on :3000 - leaving it alone."
} else {
    Start-InNewWindow -Title "Frontend (next dev :3000)" -WorkingDirectory $FrontendDir `
        -Command "npm run dev"
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
Write-Host ""
Write-Host "Remember: if this pull included a new migration, run 'alembic upgrade head'"
Write-Host "yourself in backend\ (venv active) - this script deliberately doesn't do that part."
Write-Host ""
