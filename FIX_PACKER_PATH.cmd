@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo SOH-EXTREME - Repair asset packer path only
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Fix-PackerPath.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo PACKER REPAIR FAILED - read the error above.
echo.
pause
exit /b %RESULT%
