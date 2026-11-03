@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH40-A independent Decimal mathematical certificate checker
set "PYEXE=python.exe"
python.exe -c "import sys; print(sys.executable)" >nul 2>nul
if errorlevel 1 (
 if exist "C:\Python314\python.exe" (
  set "PYEXE=C:\Python314\python.exe"
 ) else (
  echo BLOCKED: no runnable Python on PATH or C:\Python314\python.exe
  exit /b 2
 )
)
set "ARCHIVE=Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip"
if not exist "%ARCHIVE%" (
 echo BLOCKED: Original CH39 ZIP missing from same directory
 exit /b 2
)
"%PYEXE%" batch40.py "%ARCHIVE%" --out "CH40_RESULTS\CH40A_original15_results.json" --workers 3
set RC=%ERRORLEVEL%
echo CH40-A result code: %RC%
echo Result file: CH40_RESULTS\CH40A_original15_results.json
pause
exit /b %RC%
