@echo off
title Bubbles Simulation Feed
echo Starting Sim Feed to Bubbles on port 5555...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe tools\sim_feed.py 5555 50
) else (
    python tools\sim_feed.py 5555 50
)
pause
