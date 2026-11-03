@echo off
setlocal
cd /d "%~dp0"
echo Cognitum CH39 Windows read-only evidence test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Test-CH39-Windows.ps1" %*
set RC=%ERRORLEVEL%
echo.
echo Test process exit code: %RC%
echo Copy the CH39_Windows_Results folder to share diagnostics.
pause
exit /b %RC%
