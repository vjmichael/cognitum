@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VM-Gate-Menu.ps1"
set "R=%ERRORLEVEL%"
echo.
if not "%R%"=="0" echo VM gate ended with exit code %R%.
pause
exit /b %R%
