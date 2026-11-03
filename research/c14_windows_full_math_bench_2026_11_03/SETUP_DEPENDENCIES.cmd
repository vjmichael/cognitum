@echo off
setlocal
cd /d "%~dp0"
set "PY_EXE=python.exe"
where python.exe >nul 2>&1
if errorlevel 1 set "PY_EXE=C:\Python314\python.exe"
echo Optional installation: Python scientific and test dependencies, current user only.
"%PY_EXE%" -m pip install --user numpy scipy mpmath pytest cryptography
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
