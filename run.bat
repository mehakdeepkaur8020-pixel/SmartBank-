@echo off
TITLE SmartBank — Core Banking System & Hybrid AI Chatbot
echo ========================================================
echo   SmartBank: Bank Management System with AI Assistant
echo ========================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please create .venv first:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

IF NOT EXIST "smartbank.db" (
    echo [INFO] Database not found. Seeding demo data...
    .\.venv\Scripts\python.exe scripts\seed_demo_data.py
)

echo.
echo [INFO] Starting SmartBank on http://127.0.0.1:8000 ...
echo [INFO] Press Ctrl+C to stop the server.
echo.
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
pause
