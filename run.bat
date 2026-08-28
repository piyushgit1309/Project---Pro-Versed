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

REM Start application
echo Launching PRO-VERSED server on http://localhost:8000 ...
python main.py

pause
