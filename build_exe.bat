@echo off
title Rexi Desktop Companion - Standalone Builder
cd /d "%~dp0"

echo =======================================================================
echo          Rexi Desktop Companion - Standalone Portable EXE Builder
echo =======================================================================
echo.
echo Step 1: Verifying dependencies (PyQt6, google-genai, pillow, pyinstaller)...
py -3.12 -m pip install --quiet PyQt6 google-genai pillow pyinstaller

echo.
echo Step 2: Packaging rexi.pyw into a single, double-clickable .exe...
echo         - Windowless (--noconsole)
echo         - Self-contained single executable (--onefile)
echo         - Embedded rex.png and trex_icon.png graphics (--add-data)
echo.

py -3.12 -m PyInstaller ^
    --noconsole ^
    --onefile ^
    --add-data "rex.png;." ^
    --add-data "trex_icon.png;." ^
    --name "Rexi" ^
    --clean ^
    rexi.pyw

echo.
if exist "dist\Rexi.exe" (
    echo =======================================================================
    echo  SUCCESS! Your portable Windows executable is ready:
    echo  ^> "%~dp0dist\Rexi.exe"
    echo.
    echo  You can copy "dist\Rexi.exe" to any laptop or share it on GitHub!
    echo  It runs directly with no Python installation and no command prompt!
    echo =======================================================================
) else (
    echo [ERROR] Build failed. Please inspect the PyInstaller output above.
)
echo.
pause
