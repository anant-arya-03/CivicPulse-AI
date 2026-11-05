# CivicPulse AI - start the backend and frontend for local development (Windows).
# Run from the repository root:   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#
# The backend opens in a second PowerShell window (close it to stop the API).
# The frontend runs in this window (press Ctrl+C to stop it).

$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend on http://localhost:8000 (API docs: /docs) in a new window..." -ForegroundColor Cyan
Start-Process powershell -WorkingDirectory "$Root\backend" -ArgumentList @(
    "-NoExit", "-Command", ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
)

Write-Host "Starting frontend on http://localhost:3000 ..." -ForegroundColor Cyan
Set-Location "$Root\frontend"
npm run dev
