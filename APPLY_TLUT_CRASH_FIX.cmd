@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0APPLY_TLUT_CRASH_FIX.ps1" "E:\test\libultraship"
if errorlevel 1 (
  echo.
  echo PATCH FAILED - no unsafe fallback was applied.
  pause
  exit /b 1
)
echo.
echo Patch installed. Rebuild SOH now.
pause
