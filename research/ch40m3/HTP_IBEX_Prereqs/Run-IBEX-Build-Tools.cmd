@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 ( py -3 Download-IBEX-Build-Tools.py ) else ( python Download-IBEX-Build-Tools.py )
if errorlevel 1 echo Download failed; see messages above. No installation was performed.
pause

