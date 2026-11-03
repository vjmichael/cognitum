@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH40-C - independent producer-rule mathematical replay
where python.exe >nul 2>nul
if errorlevel 1 (
  if exist C:\Python314\python.exe (set "PY=C:\Python314\python.exe") else (
    echo BLOCKED: Python not found. Use your working Python installation.
    pause
    exit /b 2
  )
) else (
  set "PY=python.exe"
)
echo Python: %PY%
if not exist "Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip" (
 echo BLOCKED: sealed CH39 original source ZIP absent
 pause
 exit /b 2
)
"%PY%" batch40c.py --jobs 4 --out CH40C_RESULTS
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
 echo Benchmark failed, see CH40C_RESULTS\CH40C_SUMMARY.json
) else (
 echo Mathematics complete: CH40C_RESULTS\CH40C_SUMMARY.json
)
echo Running independent trust-policy and attack regressions...
"%PY%" -m unittest discover -s tests -p test_rule_attestation40c.py -v
if errorlevel 1 set "RC=1"
echo.
echo Final CH40-C research bench exit code: %RC%
echo No historical source or Cognitum production code was modified.
pause
exit /b %RC%
