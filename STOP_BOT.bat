@echo off
cls
echo ========================================
echo   Stopping bot...
echo ========================================
echo.

REM Ищем процесс Python с bot.py через командную строку
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr "PID:"') do (
    wmic process where "ProcessId=%%i AND CommandLine like '%%bot.py%%'" get ProcessId 2>nul | findstr /R "[0-9]" >nul
    if !errorlevel! equ 0 (
        taskkill /F /PID %%i >nul 2>&1
        echo [OK] Bot process (PID: %%i) stopped
        set STOPPED=1
    )
)

if not defined STOPPED (
    echo [INFO] Bot process not found
    echo.
    echo Tip: You can also press Ctrl+C in the bot window to stop it
)

echo.
pause
