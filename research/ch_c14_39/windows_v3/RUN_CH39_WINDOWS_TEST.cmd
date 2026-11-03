@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH39 Windows read-only evidence test - launcher fix v3
if not exist "%~dp0CH39_WINDOWS_RUNNER_V2.py" (
    echo BLOCKED: CH39_WINDOWS_RUNNER_V2.py is missing. Extract the entire ZIP first.
    set "RC=2"
    goto :finish
)
rem Prefer an actually working python.exe. A stale py.exe registration is common.
set "PYTHON_CMD="
where python.exe >nul 2>nul
if not errorlevel 1 (
    python.exe -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python.exe"
)
if defined PYTHON_CMD goto :launch
rem Explicit local fallback for the machine that reported the stale LM Studio registration.
if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=C:\Python314\python.exe"
)
if defined PYTHON_CMD goto :launch
rem Only use py.exe if its registered interpreter can actually be started.
where py.exe >nul 2>nul
if not errorlevel 1 (
    py.exe -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
    if not errorlevel 1 goto :launch_py
)
echo BLOCKED: No working Python 3.9+ interpreter was found.
echo Try running C:\Python314\python.exe directly, or repair the Python installation.
set "RC=2"
goto :finish
:launch
 echo Using verified Python: %PYTHON_CMD%
 "%PYTHON_CMD%" "%~dp0CH39_WINDOWS_RUNNER_V2.py" %*
 set "RC=%ERRORLEVEL%"
 goto :finish
:launch_py
 echo Using verified Python launcher: py.exe -3
 py.exe -3 "%~dp0CH39_WINDOWS_RUNNER_V2.py" %*
 set "RC=%ERRORLEVEL%"
:finish
echo.
echo Test process exit code: %RC%
echo Please share only the CH39_Windows_Results_* JSON and log files if needed.
pause
exit /b %RC%
