@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "SOH_BUILD_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%SOH_BUILD_POWERSHELL%" set "SOH_BUILD_POWERSHELL=powershell.exe"
"%SOH_BUILD_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_RELEASE.ps1" %*
set "SOH_BUILD_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %SOH_BUILD_EXIT%
