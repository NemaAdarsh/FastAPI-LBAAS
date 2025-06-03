@echo off

REM Create necessary directories
if not exist "haproxy_configs" mkdir haproxy_configs

REM Start services
echo Starting LBaaS services...
docker-compose up -d

echo Waiting for services to be ready...
timeout /t 10 /nobreak > nul

echo Services started!
echo API Documentation: http://localhost:8000/docs
echo HAProxy Stats: http://localhost:8404/stats
echo Health Check: http://localhost:8000/health/

pause