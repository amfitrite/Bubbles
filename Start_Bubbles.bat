@echo off
cd /d "%~dp0"
if exist "Bubbles.vbs" (
    start "" wscript.exe "Bubbles.vbs"
    exit
)
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" app.py
) else if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" app.py
) else (
    start "" pythonw.exe app.py
)
exit
