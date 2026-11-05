# CivicPulse AI - one-time setup for Windows (PowerShell 5.1+).
# Run from the repository root:   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
# What it does:
#   1. Checks Node.js and Python are installed
#   2. Creates .env from .env.example (with a random SECRET_KEY) if it doesn't exist
#   3. Creates the backend virtual environment and installs Python packages
#   4. Runs database migrations and seeds the demo user
#   5. Installs frontend npm packages

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }

Step "Checking prerequisites"
foreach ($cmd in @("node", "npm", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  '$cmd' was not found. Install it first (see docs/development.md)." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  node $(node --version), npm $(npm --version), $(python --version)"

Step "Preparing .env"
if (Test-Path ".env") {
    Write-Host "  .env already exists - leaving it unchanged."
} else {
    $secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content ".env.example") -replace "^SECRET_KEY=.*", "SECRET_KEY=$secret" |
        Set-Content ".env" -Encoding utf8
    Write-Host "  Created .env with a random SECRET_KEY. Check DATABASE_URL in it." -ForegroundColor Yellow
}

Step "Setting up the backend (Python virtual environment)"
Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "  pip install failed." -ForegroundColor Red; exit 1 }

Step "Running database migrations"
& $py -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Could not migrate the database. Is PostgreSQL running and DATABASE_URL correct?" -ForegroundColor Red
    Write-Host "  See docs/development.md section 1. Then re-run this script." -ForegroundColor Red
    exit 1
}
& $py -m scripts.seed

Step "Setting up the frontend (npm packages)"
Set-Location "$Root\frontend"
npm install
if ($LASTEXITCODE -ne 0) { Write-Host "  npm install failed." -ForegroundColor Red; exit 1 }

Set-Location $Root
Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "Start both servers with:   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1"
Write-Host "Then open http://localhost:3000  (demo login: demo@civicpulse.example / DemoPass123)"
