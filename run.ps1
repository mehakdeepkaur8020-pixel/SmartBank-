# SmartBank PowerShell Launch Script
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  SmartBank: Bank Management System with AI Assistant" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$VenvPython = ".\.venv\Scripts\python.exe"
$VenvUvicorn = ".\.venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found. Please create it first:" -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Exit 1
}

if (-not (Test-Path "smartbank.db")) {
    Write-Host "[INFO] Database not found. Seeding initial demo data..." -ForegroundColor Yellow
    & $VenvPython scripts\seed_demo_data.py
}

Write-Host ""
Write-Host "[INFO] Starting SmartBank on http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "[INFO] Press Ctrl+C to terminate the application." -ForegroundColor Gray
Write-Host ""

& $VenvUvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
