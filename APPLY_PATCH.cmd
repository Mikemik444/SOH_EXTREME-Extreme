@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "CMakeLists.txt" (
  echo ERROR: Put these files in E:\test\bb first.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_build_fix.ps1"
if errorlevel 1 (
  echo.
  echo PATCH FAILED.
  pause
  exit /b 1
)

echo.
echo Patch applied. CMake will regenerate automatically on the next build.
echo Now run build.cmd
pause
