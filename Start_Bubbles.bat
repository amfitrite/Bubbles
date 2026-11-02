@echo off
title Bubbles Terminal Launcher
cd /d "%~dp0"

:: Launch silently using pythonw.exe (windowless subsystem - zero console window)
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" app.py
) else if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" app.py
) else (
    start "" pythonw app.py
)
exit
