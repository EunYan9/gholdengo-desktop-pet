@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\pythonw.exe" (
  start "" "..\.venv\Scripts\pythonw.exe" "%~dp0main.py"
) else (
  echo Please use the existing Python environment in F:\desktop-pet\.venv.
  pause
)
