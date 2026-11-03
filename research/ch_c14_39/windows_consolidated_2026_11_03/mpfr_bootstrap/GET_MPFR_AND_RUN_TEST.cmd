@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH39 native MPFR/GMP runtime bootstrap and test
if not exist "%~dp0RUN_ALL_COGNITUM_TESTS.cmd" (
  echo ERROR: Extract BOTH files from this add-on ZIP into the existing CH23-CH39 regression kit folder.
  echo        RUN_ALL_COGNITUM_TESTS.cmd must be beside this CMD file.
  set "RC=1"
  goto finish
)
set "PY_EXE="
where.exe python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import sys, compression.zstd; sys.exit(0 if sys.version_info >= (3,14) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_EXE=python.exe"
)
if not defined PY_EXE if exist "C:\Python314\python.exe" (
  "C:\Python314\python.exe" -c "import sys, compression.zstd; sys.exit(0 if sys.version_info >= (3,14) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_EXE=C:\Python314\python.exe"
)
if not defined PY_EXE (
  echo BLOCKED: Python 3.14 with built-in compression.zstd was not found.
  set "RC=2"
  goto finish
)
echo Using verified Python: %PY_EXE%
"%PY_EXE%" "%~dp0SETUP_MPFR_RUNTIME.py" --dest "%~dp0MPFR_Runtime"
if errorlevel 1 (
  echo BLOCKED: Official native DLL download or SHA-256 check failed.
  echo See the preceding message; you can manually download both official packages
  echo beside SETUP_MPFR_RUNTIME.py and rerun.
  set "RC=2"
  goto finish
)
echo.
echo Starting all 17 prior evidence tests plus the fresh 224-bit MPFR smoke...
call "%~dp0RUN_ALL_COGNITUM_TESTS.cmd" -MathProbe -MpfrDll "%~dp0MPFR_Runtime\libmpfr-6.dll"
set "RC=%ERRORLEVEL%"
:finish
echo.
echo MPFR bootstrap and regression exit code: %RC%
if not "%RC%"=="0" echo Please send the latest COGNITUM_REGRESSION_SUMMARY.json if the test is blocked or fails.
pause
exit /b %RC%
