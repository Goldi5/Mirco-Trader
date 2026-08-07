@echo off
title 🤖 Micro-Trader System — KI-Trading Dashboard
cd /d C:\Users\goldi\projects\micro-trader
rem PYTHONPATH leeren, damit nicht die Hermes-Venv (Python 3.11-Pakete) in Python 3.12 reinkommt
set PYTHONPATH=

echo.
echo   ╔════════════════════════════════════════════════════════╗
echo   ║                                                          ║
echo   ║   🤖  MICRO TRADER SYSTEM                               ║
echo   ║       Governed AI Market Operations                     ║
echo   ║                                                          ║
echo   ║   AUDIT · RULES · LIVE GATE · LEARNING                  ║
echo   ║   v2.17.0 · Shadow-Modus · KI generiert                ║
echo   ║                                                          ║
echo   ╚════════════════════════════════════════════════════════╝
echo.
echo  ➜ Starte Dashboard auf Port 5300...
echo  ➜ http://localhost:5300
echo.

start http://localhost:5300

python dashboard.py 5300

pause
