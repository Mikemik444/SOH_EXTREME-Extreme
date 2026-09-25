@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo SOH-EXTREME - 5 SECOND ENEMY AP PICKUP MAGNET
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Apply-EnemyPickupMagnet.ps1"
if errorlevel 1 goto :fail

echo.
echo Patch installed.
echo.
echo Run your existing:
echo     build.cmd
echo.
echo After BUILD COMPLETE launch:
echo     E:\test\bb\x64\Release\soh.exe
echo.
exit /b 0

:fail
echo.
echo ============================================================
echo PATCH FAILED - no build was started.
echo ============================================================
exit /b 1
