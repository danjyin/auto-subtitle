@echo off
echo =============================================
echo  Auto Screen Subtitle — First-time setup
echo =============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo  1. Go to: https://www.python.org/downloads/
    echo  2. Download and run the installer
    echo  3. IMPORTANT: check "Add python.exe to PATH" on the first screen
    echo  4. Re-open this window and run setup.bat again
    echo.
    pause
    exit /b 1
)

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo =============================================
echo  Setup complete!
echo  Run "run.bat" to start the subtitle overlay.
echo =============================================
pause
