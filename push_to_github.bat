@echo off
title Sovereign Quant Engine - GitHub Push Helper
echo ===================================================
echo   GitHub Upload Helper for Sovereign Quant Engine
echo ===================================================
echo.

:: Check if git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
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

echo [1/5] Checking Git configuration...
git config --global user.name >nul 2>nul
if %errorlevel% neq 0 (
    echo Git user.name is not configured.
    set /p git_user="Enter your GitHub username: "
    git config --global user.name "%git_user%"
)

git config --global user.email >nul 2>nul
if %errorlevel% neq 0 (
    echo Git user.email is not configured.
    set /p git_email="Enter your GitHub email: "
    git config --global user.email "%git_email%"
)

echo.
echo [2/5] Initializing local repository...
if not exist .git (
    git init
    git branch -M main
) else (
    echo Repository already initialized.
)

echo.
echo [3/5] Setting remote repository...
git remote remove origin >nul 2>nul
git remote add origin https://github.com/pomello03/sovereign-quant-engine.git

echo.
echo [4/5] Staging files...
git add .

echo.
echo [5/5] Committing changes...
git commit -m "Initialize Sovereign Quant Engine with real-time web dashboard"

echo.
echo ===================================================
echo Ready to push to GitHub!
echo This will prompt you to log into your GitHub account.
echo ===================================================
echo.
set /p confirm="Do you want to push now? (Y/N): "
if /i "%confirm%"=="Y" (
    git push -u origin main
) else (
    echo Push aborted. You can run 'git push origin main' manually.
)

pause
