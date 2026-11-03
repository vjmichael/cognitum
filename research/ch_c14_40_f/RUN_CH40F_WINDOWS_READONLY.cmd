@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH40-F full original producer mathematical witness audit
set "PYTHON_EXE="
python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 2)" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python.exe"
if not defined PYTHON_EXE if exist "C:\Python314\python.exe" set "PYTHON_EXE=C:\Python314\python.exe"
if not defined PYTHON_EXE (
  echo ERROR: Python 3.11+ not found. No tests run.
  pause
  exit /b 2
)
echo Using: %PYTHON_EXE%
"%PYTHON_EXE%" "%~dp0windows_readonly40f.py" %*
set "TEST_EXIT=%ERRORLEVEL%"
echo CH40-F Windows test exit code: %TEST_EXIT%
echo Result: CH40F_WINDOWS_RESULTS\CH40F_WINDOWS_REPLAY_RESULTS.json
pause
exit /b %TEST_EXIT%
