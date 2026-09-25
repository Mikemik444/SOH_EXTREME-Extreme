@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo SOH-EXTREME - SAFE BUILD + APWORLD SOURCE SYNC
echo ============================================================
echo.

if not exist "CMakeLists.txt" (
    echo ERROR: build.cmd is not in the SOH-EXTREME source root.
    echo Put this file directly in E:\test\bb next to CMakeLists.txt.
    exit /b 1
)

if not exist "build-vs" (
    echo ERROR: build-vs was not found next to this script.
    exit /b 1
)

if not exist "archipelago\soh_extreme\__init__.py" (
    echo ERROR: Canonical APWorld source was not found:
    echo   %CD%\archipelago\soh_extreme\__init__.py
    echo.
    echo The source folder must be named archipelago, not arvhipelago.
    exit /b 1
)

echo [0/7] Rebuilding and installing SOH-EXTREME APWorld from archipelago\...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\build_standalone_apworld.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto :fail

echo.
echo [1/7] Installing/verifying official Archipelago item model assets...
if exist ".\install_official_ap_model_assets.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File ".\install_official_ap_model_assets.ps1"
    if errorlevel 1 goto :fail
) else (
    echo WARNING: install_official_ap_model_assets.ps1 was not found; continuing.
)

echo.
echo [2/7] Rebuilding soh.o2r...
echo NOTE: This stage intentionally uses one build worker.
echo       CMake/FetchContent regeneration can otherwise launch overlapping
echo       ZERO_CHECK projects and lock their .tlog files.
cmake --build build-vs --config Release --target GenerateSohOtr --parallel 4
if errorlevel 1 goto :fail

if not exist "%CD%\build-vs\soh\soh.o2r" (
    echo ERROR: %CD%\build-vs\soh\soh.o2r was not generated.
    goto :fail
)

echo.
echo [3/7] Building the Release executable...
cmake --build build-vs --config Release --target soh --parallel 8
if errorlevel 1 goto :fail

echo.
echo [4/7] Copying the fresh soh.o2r to runtime locations...
copy /Y "%CD%\build-vs\soh\soh.o2r" "%CD%\soh.o2r" >nul
if errorlevel 1 goto :fail

if exist "%CD%\build-vs\Release" (
    copy /Y "%CD%\build-vs\soh\soh.o2r" "%CD%\build-vs\Release\soh.o2r" >nul
    if errorlevel 1 goto :fail
)

if exist "%CD%\build-vs\soh\Release" (
    copy /Y "%CD%\build-vs\soh\soh.o2r" "%CD%\build-vs\soh\Release\soh.o2r" >nul
    if errorlevel 1 goto :fail
)

if exist "%CD%\x64\Release" (
    copy /Y "%CD%\build-vs\soh\soh.o2r" "%CD%\x64\Release\soh.o2r" >nul
    if errorlevel 1 goto :fail
)

echo.
echo [5/7] Copying the fresh executable to the source-root runtime...
set "FRESH_EXE="

if exist "%CD%\x64\Release\soh.exe" set "FRESH_EXE=%CD%\x64\Release\soh.exe"
if not defined FRESH_EXE if exist "%CD%\build-vs\Release\soh.exe" set "FRESH_EXE=%CD%\build-vs\Release\soh.exe"
if not defined FRESH_EXE if exist "%CD%\build-vs\soh\Release\soh.exe" set "FRESH_EXE=%CD%\build-vs\soh\Release\soh.exe"

if not defined FRESH_EXE (
    echo ERROR: Could not find the newly built soh.exe.
    echo Checked:
    echo   %CD%\x64\Release\soh.exe
    echo   %CD%\build-vs\Release\soh.exe
    echo   %CD%\build-vs\soh\Release\soh.exe
    goto :fail
)

copy /Y "%FRESH_EXE%" "%CD%\soh.exe" >nul
if errorlevel 1 goto :fail

if exist "%CD%\x64\Release\APCpp.dll" copy /Y "%CD%\x64\Release\APCpp.dll" "%CD%\APCpp.dll" >nul
if exist "%CD%\build-vs\Release\APCpp.dll" copy /Y "%CD%\build-vs\Release\APCpp.dll" "%CD%\APCpp.dll" >nul
if exist "%CD%\build-vs\soh\Release\APCpp.dll" copy /Y "%CD%\build-vs\soh\Release\APCpp.dll" "%CD%\APCpp.dll" >nul

echo.
echo [6/7] Runtime/APWorld verification...
for %%F in ("%FRESH_EXE%") do echo Fresh EXE: %%~fF  %%~zF bytes
for %%F in ("%CD%\soh.exe") do echo Root  EXE: %%~fF  %%~zF bytes
for %%F in ("%CD%\soh.o2r") do echo Root  O2R: %%~fF  %%~zF bytes
for %%F in ("%CD%\soh_extreme.apworld") do echo APWorld: %%~fF  %%~zF bytes

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\tools\build_standalone_apworld.ps1" -ProjectRoot "%CD%" -CheckOnly
if errorlevel 1 goto :fail

echo.
echo [7/7] Done.
echo ============================================================
echo BUILD COMPLETE
echo.
echo IMPORTANT:
echo   Restart Archipelago after this build.
echo   Generate a NEW seed/room using the newly installed APWorld.
echo.
echo Launch: %CD%\soh.exe
echo ============================================================
exit /b 0

:fail
echo.
echo ============================================================
echo BUILD FAILED - scroll up to the FIRST error.
echo ============================================================
exit /b 1
