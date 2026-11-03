@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH40-D independent local mathematical proof witnesses
where python.exe >nul 2>nul
if errorlevel 1 (
  if exist "C:\Python314\python.exe" (
    set "PY=C:\Python314\python.exe"
  ) else (
    echo BLOCKED: Python 3 not found. No mathematical result has been certified.
    pause
    exit /b 2
  )
) else (
  set "PY=python.exe"
)
"%PY%" -c "import sys;assert sys.version_info >= (3,11)" >nul 2>nul
if errorlevel 1 (
 echo BLOCKED: Need Python 3.11+; no test executed.
 pause
 exit /b 2
)
set "PYTHONPATH=%~dp0"
echo Recomputing original 15 x 4 certificate types from frozen CH39 data ...
"%PY%" -u batch40d.py --archive "%~dp0Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip" --jobs 1 --out "%~dp0CH40D_RESULTS"
if errorlevel 1 (
 echo FAIL: mathematical producer/verifier disagreement, check CH40D_RESULTS.
 pause
 exit /b 1
)
echo Re-verifying every exported proof certificate without trusting saved receipts ...
"%PY%" -u finalize40d.py --out "%~dp0CH40D_RESULTS"
set "CODE=%ERRORLEVEL%"
echo CH40-D test exit code %CODE%
echo Report: CH40D_RESULTS\CH40D_FINAL_ACCEPTANCE.json
echo Windows local proof check does NOT certify old producer caps or unrestricted global optimum.
pause
exit /b %CODE%
