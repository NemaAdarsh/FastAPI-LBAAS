@echo off
REM FastAPI Load Balancer Service - Windows Startup Script

echo Starting FastAPI Load Balancer Service...
echo ==========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "config" mkdir config
if not exist "data" mkdir data
if not exist "haproxy_configs" mkdir haproxy_configs

REM Set environment variables for development
set ENV=development
set DEBUG=true
set DATABASE_URL=sqlite:///./app.db
set SECRET_KEY=your-secret-key-change-in-production

REM Start Docker services if available
echo Checking for Docker services...
docker-compose up -d 2>nul
if errorlevel 1 (
    echo Warning: Docker services not available
) else (
    echo Waiting for Docker services to be ready...
    timeout /t 10 /nobreak > nul
)

REM Start the FastAPI application
echo Starting FastAPI application...
python startup.py --host 0.0.0.0 --port 8000

echo.
echo Services started!
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health/
echo.

pause