@echo off
cls
echo ========================================
echo   Stopping bot...
echo ========================================
echo.

taskkill /F /IM python.exe /FI "WINDOWTITLE eq *bot.py*" 2>nul

if %errorlevel% equ 0 (
    echo [OK] Bot stopped
) else (
    echo [INFO] Bot process not found
)

echo.
pause
