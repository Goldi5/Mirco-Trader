@echo off
title 📈 Micro-Trading Batch
cd /d C:\Users\goldi\projects\micro-trader
rem PYTHONPATH leeren, damit nicht die Hermes-Venv (Python 3.11-Pakete) in Python 3.12 reinkommt
set PYTHONPATH=

echo.
echo   ╔═══════════════════════════════════╗
echo   ║  📈 20 Depots auswerten           ║
echo   ╚═══════════════════════════════════╝
echo.
echo  Start: %date% %time%
echo.

python batch_trader.py

echo.
echo  Fertig. Drücke eine Taste...
pause >nul
