@echo off
setlocal
cd /d "%~dp0"
where python.exe >nul 2>&1
if errorlevel 1 (
 if exist "C:\Python314\python.exe" (set "PY=C:\Python314\python.exe") else (echo ERROR: Python not found & pause & exit /b 2)
) else (set "PY=python.exe")
echo Cognitum CH40-E read-only independent research trace verification
"%PY%" audit40e.py --full127
set "RET=%ERRORLEVEL%"
echo Exit code: %RET%
echo Report: CH40E_READONLY_RESULTS\CH40E_READONLY_AUDIT.json
pause
exit /b %RET%
