@echo off
REM Launcher for Rexi Desktop Companion
cd /d "%~dp0"
if exist "rexi.pyw" (
    start "" py -3.12 rexi.pyw
) else (
    start "" py -3.12 rex.pyw
)
