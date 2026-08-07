@echo off
title 📈📊 Micro-Trader
cd /d C:\Users\goldi\projects\micro-trader
rem PYTHONPATH leeren, damit nicht die Hermes-Venv (Python 3.11-Pakete) in Python 3.12 reinkommt
set PYTHONPATH=

echo.
echo   ╔═══════════════════════════════════╗
echo   ║     📈📊 MICRO-TRADER              ║
echo   ╚═══════════════════════════════════╝
echo.
echo  [1/3] Starte Dashboard (Port 5300)...
start /B python dashboard.py 5300 >nul 2>&1
timeout /t 2 /nobreak >nul

echo  [2/3] Oeffne Browser...
start http://localhost:5300

echo  [3/3] Batch-Lauf......
python batch_trader.py --quiet
echo.
echo  ✅ Dashboard: http://localhost:5299
echo.
pause
