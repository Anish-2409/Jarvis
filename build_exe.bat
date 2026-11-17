@echo off
title Jarvis Desktop Companion - Standalone Builder
cd /d "%~dp0"

echo =======================================================================
echo          Jarvis Desktop Companion - Standalone Portable EXE Builder
echo =======================================================================
echo.
echo Step 1: Verifying dependencies (PyQt6, google-genai, pillow, pyinstaller, edge-tts, pygame, sounddevice)...
py -3.12 -m pip install --quiet PyQt6 google-genai pillow pyinstaller edge-tts pygame sounddevice pvporcupine speechrecognition

echo.
echo Step 2: Packaging jarvis.pyw into a single, double-clickable .exe...
echo         - Windowless (--noconsole)
echo         - Self-contained single executable (--onefile)
echo         - Embedded Wallpaper.png graphic
echo.

py -3.12 -m PyInstaller Jarvis.spec

echo.
if exist "dist\Jarvis.exe" (
    echo =======================================================================
    echo  SUCCESS! Your portable Windows executable is ready:
    echo  ^> "%~dp0dist\Jarvis.exe"
    echo.
    echo  You can copy "dist\Jarvis.exe" to any laptop or share it on GitHub!
    echo  It runs directly with no Python installation and no command prompt!
    echo =======================================================================
) else (
    echo [ERROR] Build failed. Please inspect the PyInstaller output above.
)
echo.
pause
