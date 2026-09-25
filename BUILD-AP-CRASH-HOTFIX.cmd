@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "tools\build_ap_crash_hotfix.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto failed
echo.
echo AP crash hotfix built and deployed. Keep your current AP world, assets, and seed.
exit /b 0
:failed
echo.
echo HOTFIX BUILD FAILED. No build folders, assets, or saves were deleted.
echo Read the first error above. Do not start an older EXE while this build is failing.
exit /b 1
