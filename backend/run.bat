@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" copy ".env.example" ".env" >nul

if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" app.py
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  py app.py
)

endlocal
