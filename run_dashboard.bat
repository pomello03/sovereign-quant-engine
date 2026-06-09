@echo off
title Sovereign Quant Engine - Dashboard Launcher
echo ===================================================
echo   Starting Sovereign Quant Engine Web Dashboard...
echo ===================================================
echo.

:: Launch the FastAPI server in a separate background command window
start "Sovereign Web Server" cmd /c "python web_dashboard/main.py"

:: Wait for 2 seconds to allow Uvicorn to initialize
echo Waiting for server to spin up...
timeout /t 2 /nobreak >nul

:: Open the default web browser to the local server URL
echo Launching default browser at http://127.0.0.1:8000 ...
start http://127.0.0.1:8000

echo.
echo ===================================================
echo   Dashboard started! You can close this window.
echo ===================================================
pause
