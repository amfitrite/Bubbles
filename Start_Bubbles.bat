@echo off
title Bubbles - Order Flow Terminal
echo ====================================================
echo Starting Bubbles Terminal (Monochrome Matte Studio)
echo Ports: 5555..5559 [MT5 Multi-Port Bridge]
echo ====================================================
echo.

:: Check virtual environment
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe app.py
) else (
    python app.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%
    pause
)
