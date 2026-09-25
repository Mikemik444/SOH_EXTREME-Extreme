@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo SOH-EXTREME 0.11.22 - Soul Visibility and Grab Logic
echo Close the game and Universal Tracker before continuing.
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Apply-SoulVisibilityGrabFix.ps1"
if errorlevel 1 (
    echo.
    echo PATCH OR BUILD FAILED - read the error above.
    pause
    exit /b 1
)
echo.
pause
exit /b 0
