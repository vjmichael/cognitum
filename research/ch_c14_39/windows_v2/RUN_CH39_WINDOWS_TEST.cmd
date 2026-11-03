@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH39 Windows read-only test - revised v2
where py.exe >nul 2>nul
if not errorlevel 1 goto :with_py
where python.exe >nul 2>nul
if not errorlevel 1 goto :with_python
echo BLOCKED: Python 3.9 or newer could not be found.
echo Download Python or ensure py.exe/python.exe is on PATH.
set "RC=2"
goto :finish
:with_py
py.exe -3 "%~dp0CH39_WINDOWS_RUNNER_V2.py" %*
set "RC=%ERRORLEVEL%"
goto :finish
:with_python
python.exe "%~dp0CH39_WINDOWS_RUNNER_V2.py" %*
set "RC=%ERRORLEVEL%"
:finish
echo.
echo Test process exit code: %RC%
echo Please share only the CH39_Windows_Results_* JSON and log files if needed.
pause
exit /b %RC%
