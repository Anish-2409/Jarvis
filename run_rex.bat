@echo off
REM Launcher for Jarvis Desktop Companion (Legacy Rex alias)
cd /d "%~dp0"
if exist "jarvis.pyw" (
    start "" py -3.12 jarvis.pyw
) else (
    start "" py -3.12 rexi.pyw
)
