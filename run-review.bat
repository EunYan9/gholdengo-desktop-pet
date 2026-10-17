@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0setup.bat"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0codex-pet\review.py" --gholdengo --demo
