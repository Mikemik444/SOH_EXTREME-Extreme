@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PATCH_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PATCH_POWERSHELL%" set "PATCH_POWERSHELL=powershell.exe"
"%PATCH_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0APPLY_AND_BUILD.ps1" %*
set "PATCH_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %PATCH_EXIT%
