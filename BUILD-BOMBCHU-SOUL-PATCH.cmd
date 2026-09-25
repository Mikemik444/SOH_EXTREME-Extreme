@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 exit /b 1
if not exist "CMakeLists.txt" (
  echo Extract this patch into the project root, beside soh, src, assets, and CMakeLists.txt.
  exit /b 1
)
if not exist "build-vs\CMakeCache.txt" (
  echo Your existing build-vs configuration was not found. Configure the project using your normal toolchain first.
  exit /b 1
)
where cmake >nul 2>&1
if errorlevel 1 (
  echo CMake is not available in this Command Prompt.
  exit /b 1
)
echo [1/4] Refreshing the existing build configuration...
cmake -S . -B build-vs
if errorlevel 1 goto failed
echo [2/4] Rebuilding the custom asset archive with one worker...
cmake --build build-vs --config Release --target GenerateSohOtr --parallel 1
if errorlevel 1 goto failed
echo [3/4] Building the Release executable...
cmake --build build-vs --config Release --parallel 8
if errorlevel 1 goto failed
echo [4/4] Verifying all 47 packed soul textures and copying the built game...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "tools\deploy_bombchu_soul_build.ps1" -ProjectRoot "%CD%"
if errorlevel 1 goto failed
echo.
echo Build and asset verification completed. Replace the installed AP world separately.
exit /b 0
:failed
echo.
echo BUILD OR ASSET VERIFICATION FAILED. No build folders were deleted.
echo Scroll up to the first error. Close any other build jobs before retrying.
exit /b 1
