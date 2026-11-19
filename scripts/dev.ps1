# CivicPulse AI - start the backend and frontend for local development (Windows).
# Run from the repository root:   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#
param(
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000
)

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$Frontend = Join-Path $Root 'frontend'
$BackendUrl = "http://127.0.0.1:$BackendPort"

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Backend Python is missing. Run scripts\setup.ps1 first.'
}
& $Python -c 'import sys; sys.exit(sys.version_info < (3, 11))'
if ($LASTEXITCODE -ne 0) {
    throw 'Backend Python is broken or too old. Recreate backend\.venv with Python 3.11 or newer and run scripts\setup.ps1.'
}

if ([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners().Port -contains $BackendPort) {
    throw "Port $BackendPort is already in use. Stop the other process or choose a free port with -BackendPort."
}

Write-Host "Starting CivicPulse API at $BackendUrl ..." -ForegroundColor Cyan
$Backend = Start-Process -FilePath $Python -WorkingDirectory "$Root\backend" -ArgumentList @(
    '-m', 'uvicorn', 'app.main:app', '--reload', '--port', $BackendPort
) -WindowStyle Hidden -PassThru -RedirectStandardError "$Root\backend\dev-api.log"

$PreviousBackendUrl = $env:BACKEND_URL
try {
    $Health = $null
    for ($Attempt = 0; $Attempt -lt 30 -and -not $Backend.HasExited; $Attempt++) {
        try {
            $Health = Invoke-RestMethod "$BackendUrl/api/v1/health" -TimeoutSec 3 -ErrorAction Stop
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if ($Health.database -ne 'ok') {
        throw 'CivicPulse API is not ready. Check PostgreSQL, run scripts\setup.ps1 for migrations, and see backend\dev-api.log.'
    }

    $env:BACKEND_URL = $BackendUrl
    Write-Host "Starting frontend on http://localhost:3000 ..." -ForegroundColor Cyan
    Push-Location $Frontend
    try {
        npm run dev
    } finally {
        Pop-Location
    }
} finally {
    $env:BACKEND_URL = $PreviousBackendUrl
    if (-not $Backend.HasExited) {
        taskkill.exe /PID $Backend.Id /T /F | Out-Null
    }
}
