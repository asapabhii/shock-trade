# Shock Trade - Start Script for Windows PowerShell
# This script starts both the backend API and frontend dev server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Shock Trade - Starting Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Copy .env.example to .env and add your API keys" -ForegroundColor Yellow
    Write-Host ""
}

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    .\venv\Scripts\pip.exe install -r requirements.txt
}

# Check if node_modules exists
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "Starting Backend API on http://localhost:8000" -ForegroundColor Green
Write-Host "Starting Frontend on http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Supported Sports: NFL, NBA, NHL, MLB, Soccer" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Start backend in background
$backend = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "scripts/run_server.py" -PassThru -NoNewWindow

# Start frontend
Push-Location frontend
npm run dev
Pop-Location

# Cleanup on exit
Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
