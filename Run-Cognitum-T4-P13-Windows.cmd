@echo off
setlocal
cd /d "%~dp0"
set "GATE_EVIDENCE=%CD%\Cognitum_T4_P13_Windows_Evidence"
if exist "%GATE_EVIDENCE%" (
  echo Evidence directory already exists. Preserve it, then choose a fresh checkpoint copy.
  exit /b 2
)
where python >nul 2>nul || ( echo Python is required and was not found. & exit /b 2 )
python -m tools.run_c15_t4_p13_windows_gate --output "%GATE_EVIDENCE%"
set "RESULT=%ERRORLEVEL%"
echo.
echo P13 exit code: %RESULT%. This does NOT validate real issuer identity, physics or OS isolation.
pause
exit /b %RESULT%
