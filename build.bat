@echo off
echo Building Bluetooth Battery Monitor...
echo.

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building executable...
pyinstaller build.spec

echo.
echo Build complete! Executable is in the dist folder.
pause
