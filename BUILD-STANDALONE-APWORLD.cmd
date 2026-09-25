@echo off
setlocal
cd /d "%~dp0"
echo Building and installing SOH-EXTREME 0.11.1 standalone APWorld...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_standalone_apworld.ps1"
if errorlevel 1 (
    echo.
    echo BUILD FAILED. See the error above.
    pause
    exit /b 1
)
echo.
echo Finished. You can now run Archipelago Generate again.
pause
