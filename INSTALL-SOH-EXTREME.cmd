@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   SOH-EXTREME 0.11.9 standalone APWorld installer
echo ============================================================
echo.
echo This builds the FINAL standalone soh_extreme.apworld and installs it.
echo Do NOT copy the file under source\ into Archipelago custom_worlds.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_standalone_apworld.ps1"
if errorlevel 1 (
    echo.
    echo INSTALL FAILED. Copy the full error above back to ChatGPT.
    pause
    exit /b 1
)
echo.
echo SUCCESS. You can run Archipelago Generate now.
pause
