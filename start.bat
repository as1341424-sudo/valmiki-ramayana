@echo off
title Sri Valmiki Ramayana — Starting Server...
color 1F
echo.
echo  ========================================
echo    Sri Valmiki Ramayana — Local Server
echo  ========================================
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Please install Python 3.10+
    echo  Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Install dependencies silently if needed
echo  [1/2] Checking dependencies...
pip install -r requirements.txt -q --disable-pip-version-check

:: Start the server
echo  [2/2] Starting server...
echo.
echo  ----------------------------------------
echo   Open your browser and go to:
echo   http://localhost:5000
echo.
echo   Username : admin
echo   Password : ramayana2024
echo  ----------------------------------------
echo.
echo  Press Ctrl+C to stop the server.
echo.

:: Auto-open browser after 3 seconds
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"

python server/api.py

pause
