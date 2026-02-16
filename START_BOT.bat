@echo off
cls
echo ========================================
echo   Obsidian Telegram Bot
echo ========================================
echo.

cd /d "%~dp0"

set PYTHON=C:\Users\Maksim\AppData\Local\Programs\Python\Python314\python.exe

echo Checking Python...
"%PYTHON%" --version
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

echo [OK] Python found
echo.

echo Installing dependencies...
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install --upgrade aiogram PyGithub python-dotenv --quiet

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] All dependencies installed
echo.
echo ========================================
echo         STARTING BOT
echo ========================================
echo.
echo Bot is running. Press Ctrl+C to stop
echo.

"%PYTHON%" bot.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Bot stopped with error
)

echo.
pause
