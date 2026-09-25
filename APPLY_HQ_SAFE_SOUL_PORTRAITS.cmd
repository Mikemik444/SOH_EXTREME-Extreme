@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo SOH-EXTREME - HQ SAFE SOUL PORTRAITS
echo ============================================================
echo.
echo This generates 64x64-detail enemy portraits as FOUR safe
echo 32x32 RGBA32 textures. It does not modify build.cmd or APWorld.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\GenerateSoulPortraitTiles.ps1"
if errorlevel 1 goto :fail

echo.
echo Portrait tiles generated. Starting your existing build.cmd...
call "%~dp0build.cmd"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo COMPLETE
echo Run: E:\test\bb\x64\Release\soh.exe
echo ============================================================
exit /b 0

:fail
echo.
echo ============================================================
echo FAILED - scroll up to the first error.
echo ============================================================
exit /b 1
