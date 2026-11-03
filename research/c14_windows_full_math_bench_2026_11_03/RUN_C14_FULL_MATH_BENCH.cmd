@echo off
setlocal
cd /d "%~dp0"
echo Cognitum CH23-CH39: FULL MATHEMATICAL BENCHMARK
set "PY_EXE="
where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe -c "import sys;assert sys.version_info >= (3,11)" >nul 2>&1
  if not errorlevel 1 set "PY_EXE=python.exe"
)
if not defined PY_EXE if exist "C:\Python314\python.exe" set "PY_EXE=C:\Python314\python.exe"
if not defined PY_EXE (
 echo BLOCKED: working Python 3 not found.
 pause
 exit /b 2
)
echo Python: %PY_EXE%
"%PY_EXE%" "%~dp0C14_MATH_BENCH.py" %*
set "RC=%ERRORLEVEL%"
echo.
echo Benchmark exit: %RC%
echo Results and logs: C14_MATH_RESULTS\
pause
exit /b %RC%
