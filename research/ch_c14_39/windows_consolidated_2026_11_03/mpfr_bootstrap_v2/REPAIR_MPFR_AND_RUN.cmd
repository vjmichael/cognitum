@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Cognitum CH39 native MPFR / GMP DLL dependency repair - v2
if not exist "%~dp0RUN_ALL_COGNITUM_TESTS.cmd" (
  echo ERROR: Place this helper beside RUN_ALL_COGNITUM_TESTS.cmd in your extracted consolidated regression folder.
  set "RC=1"
  goto done
)
set "PY_EXE="
where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import sys, compression.zstd; sys.exit(0 if sys.version_info >= (3,14) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_EXE=python.exe"
)
if not defined PY_EXE if exist "C:\Python314\python.exe" (
  "C:\Python314\python.exe" -c "import sys, compression.zstd; sys.exit(0 if sys.version_info >= (3,14) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_EXE=C:\Python314\python.exe"
)
if not defined PY_EXE (
  echo BLOCKED: Python 3.14 or compression.zstd unavailable.
  set "RC=2"
  goto done
)
echo Using verified Python: %PY_EXE%
"%PY_EXE%" "%~dp0SETUP_MPFR_RUNTIME_V2.py" --dest "%~dp0MPFR_Runtime" --offline-dir "%~dp0"
if errorlevel 1 (
  set "RC=2"
  echo BLOCKED: DLL setup or Windows loader check failed. Upload MPFR_Runtime\MPFR_RUNTIME_DIAGNOSTICS_V2.json.
  goto done
)
echo.
echo All native DLL loads passed. Running CH23-CH39 evidence regression + 7-node MPFR smoke.
call "%~dp0RUN_ALL_COGNITUM_TESTS.cmd" -MathProbe -MpfrDll "%~dp0MPFR_Runtime\libmpfr-6.dll"
set "RC=%ERRORLEVEL%"
:done
echo.
echo MPFR Windows repair/test exit code: %RC%
if not "%RC%"=="0" echo Share summary JSON and MPFR_RUNTIME_DIAGNOSTICS_V2.json only.
pause
exit /b %RC%
