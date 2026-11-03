@echo off
setlocal
cd /d "%~dp0"
echo Cognitum C14 CH40-B Independent Decimal, Likelihood-Fisher, Taylor, Newton test
set "PYCMD=python.exe"
"%PYCMD%" -c "import sys;print(sys.version)" >nul 2>&1
if errorlevel 1 (
  if exist "C:\Python314\python.exe" (set "PYCMD=C:\Python314\python.exe") else (
    echo BLOCKED: Python executable unavailable. No tests run.
    pause
    exit /b 2
  )
)
echo Running independent mathematical and forged-proof unit tests...
"%PYCMD%" -m unittest discover -s tests -p test_ch40b.py -v >CH40B_WINDOWS_TESTS.log 2>&1
set "TEST_ERR=%ERRORLEVEL%"
type CH40B_WINDOWS_TESTS.log
if not "%TEST_ERR%"=="0" (
 echo FAIL: CH40-B unit tests did not pass, refusing original-case acceptance.
 pause
 exit /b %TEST_ERR%
)
echo Running all 15 frozen originals with independent Decimal bounds...
"%PYCMD%" batch40b.py --jobs 4 --out CH40B_WINDOWS_ORIGINAL15_RESULTS.json
set "RESULT=%ERRORLEVEL%"
echo Result exit code: %RESULT%
echo Reports: CH40B_WINDOWS_ORIGINAL15_RESULTS.json and CH40B_WINDOWS_TESTS.log
pause
exit /b %RESULT%
