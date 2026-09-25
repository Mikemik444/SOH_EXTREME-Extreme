@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo SOH-EXTREME - Asset Build and arvhipelago Source Sync
echo Close the game and Universal Tracker before continuing.
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Apply-BuildSourceFix.ps1"
if errorlevel 1 (
    echo.
    echo FIX OR BUILD FAILED - read the first error above.
    pause
    exit /b 1
)
echo.
echo COMPLETE - use the soh.exe beside this script.
pause
exit /b 0
