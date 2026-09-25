@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo SOH-EXTREME - Shovel / Roll graphics and APCpp request safety
echo Close the game before continuing.
echo ============================================================
if not exist "CMakeLists.txt" (
    echo ERROR: Extract the ZIP directly into E:\test\bb, not into a subfolder.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_shovel_roll_crash_fix.ps1"
if errorlevel 1 goto :fail
rem Keep both generations of the compiler environment workaround safe.
rem _CL_ is appended after project switches, so /MP1 wins over an old /MP.
set "CL=/FS /MP1"
set "_CL_=/FS /MP1"
echo.
echo Rebuilding with your existing build.cmd...
call "%~dp0build.cmd"
if errorlevel 1 goto :fail
echo.
echo Launch THIS executable: "%~dp0soh.exe"
echo Do not use an older copy in x64\Release2; its APCpp.dll is separate.
pause
exit /b 0
:fail
echo.
echo PATCH OR BUILD FAILED. Copy the first error above.
pause
exit /b 1
