@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\apply_0_11_21d_house_pots.ps1" -Root "%~dp0"
if errorlevel 1 (
    echo.
    echo ============================================================
    echo PATCH FAILED - no build was started.
    echo ============================================================
    exit /b 1
)

echo.
echo Source patch applied. Rebuild with:
echo   cmake --build build-vs --config Release --parallel 8
endlocal
