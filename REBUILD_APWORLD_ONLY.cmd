@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo SOH-EXTREME - REBUILD / INSTALL APWORLD ONLY
echo ============================================================
echo.

if not exist "archipelago\soh_extreme\__init__.py" (
    echo ERROR: Missing %CD%\archipelago\soh_extreme\__init__.py
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\build_standalone_apworld.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto :fail

echo.
echo APWorld rebuilt and installed successfully.
echo Close and reopen Archipelago, then generate a NEW seed.
exit /b 0

:fail
echo.
echo APWorld rebuild/install failed.
exit /b 1
