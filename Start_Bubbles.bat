@echo off
echo ==========================================
echo Starting Bubbles - Hybrid Micro/Macro Order Flow
echo ==========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10 or higher.
    pause
    exit /b
)

:: Setup Virtual Environment if it doesn't exist
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

:: Activate Virtual Environment
call venv\Scripts\activate.bat

:: Install Requirements
echo [INFO] Checking dependencies...
pip install -r requirements.txt

:: Start Application
echo.
echo [INFO] Starting Application on Port 5558...
python app.py

:: Deactivate upon exit
deactivate
pause
