@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-paytracker.ps1"
if errorlevel 1 (
  echo.
  echo PayTracker could not start. Review the message above.
  pause
)
endlocal

