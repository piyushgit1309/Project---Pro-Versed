@echo off
REM ==============================================================================
REM PRO-VERSED Platform Launch Script (Windows)
REM National Student Innovation Platform & Project Showcase
REM ==============================================================================

echo ======================================================================
echo  Starting PRO-VERSED Platform...
echo  National Student Innovation Platform & Project Showcase
echo ======================================================================

cd /d "%~dp0"

REM Check Python availability
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is required but not found in PATH.
    pause
    exit /b 1
)

REM Setup virtual environment if missing
if not exist "venv" (\
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Install dependencies
echo [2/3] Installing/verifying requirements...
pip install -r backend\requirements.txt --quiet

REM Start application
echo [3/3] Launching PRO-VERSED server on http://localhost:8000 ...
cd backend
set PROVERSED_DB_PATH=%TEMP%\proversed.db
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
