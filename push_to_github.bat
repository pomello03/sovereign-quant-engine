@echo off
title Sovereign Quant Engine - GitHub Push Helper
echo ===================================================
echo   GitHub Upload Helper for Sovereign Quant Engine
echo ===================================================
echo.

:: Ensure working directory is the script's directory
cd /d "%~dp0"

:: Detect if we have global git or local portable git
set "GIT_CMD=git"
where git >nul 2>nul
if %errorlevel% neq 0 (
    if exist "bin\MinGit\cmd\git.exe" (
        set "GIT_CMD=bin\MinGit\cmd\git.exe"
        echo [INFO] Local portable Git detected at bin\MinGit\cmd\git.exe
    ) else (
        echo [ERROR] Git is not installed or not in your PATH.
        echo Please install Git for Windows from: https://git-scm.com/download/win
        echo.
        echo Opening the download link in your browser...
        start https://git-scm.com/download/win
        echo.
        echo After installing, please close and reopen this terminal, then run this file again.
        pause
        exit /b 1
    )
)

echo [1/5] Checking Git configuration...
%GIT_CMD% config --local user.name >nul 2>nul
if %errorlevel% neq 0 (
    echo Git user.name is not configured locally.
    %GIT_CMD% config --local user.name "pomello03"
    echo Configured local user.name to: pomello03
)

%GIT_CMD% config --local user.email >nul 2>nul
if %errorlevel% neq 0 (
    echo Git user.email is not configured locally.
    %GIT_CMD% config --local user.email "pomello03@users.noreply.github.com"
    echo Configured local user.email to: pomello03@users.noreply.github.com
)

echo.
echo [2/5] Initializing local repository...
if not exist .git (
    %GIT_CMD% init
    %GIT_CMD% branch -M main
) else (
    echo Repository already initialized.
)

echo.
echo [3/5] Setting remote repository...
%GIT_CMD% remote remove origin >nul 2>nul
%GIT_CMD% remote add origin https://github.com/pomello03/sovereign-quant-engine.git

echo.
echo [4/5] Staging files...
%GIT_CMD% add .

echo.
echo [5/5] Committing changes...
%GIT_CMD% commit -m "Initialize Sovereign Quant Engine with real-time web dashboard"

echo.
echo ===================================================
echo Ready to push to GitHub!
echo This will prompt you to log into your GitHub account.
echo ===================================================
echo.
set /p confirm="Do you want to push now? (Y/N): "
if /i "%confirm%"=="Y" (
    %GIT_CMD% push -u origin main
) else (
    echo Push aborted. You can run '%GIT_CMD% push origin main' manually.
)

pause
