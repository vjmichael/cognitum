@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH23 - CH39 consolidated Windows regression
set "PY_EXE="
where.exe python.exe >nul 2>nul
if not errorlevel 1 (
    python.exe -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_EXE=python.exe"
)
if defined PY_EXE goto run_python
if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_EXE=C:\Python314\python.exe"
)
if defined PY_EXE goto run_python
where.exe py.exe >nul 2>nul
if not errorlevel 1 (
    py.exe -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
    if not errorlevel 1 goto run_launcher
)
echo BLOCKED: No working Python 3.9 or newer. Try C:\Python314\python.exe
set "RC=2"
goto finish
:run_python
echo Running with %PY_EXE%
"%PY_EXE%" "%~dp0COGNITUM_HISTORY_REGRESSION.py" %*
set "RC=%ERRORLEVEL%"
goto finish
:run_launcher
echo Running with validated py.exe -3
py.exe -3 "%~dp0COGNITUM_HISTORY_REGRESSION.py" %*
set "RC=%ERRORLEVEL%"
:finish
echo.
echo Regression exit code: %RC%
echo Share only COGNITUM_REGRESSION_SUMMARY.json and ERROR.log if needed.
pause
exit /b %RC%
