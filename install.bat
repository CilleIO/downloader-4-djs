@echo off
echo Multi-Platform Music Downloader - Installation Script
echo =====================================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Python found!
echo.

echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Checking FFmpeg installation...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo WARNING: FFmpeg not found in PATH
    echo.
    echo FFmpeg is required for audio processing.
    echo Please install FFmpeg from https://ffmpeg.org/download.html
    echo and add it to your system PATH.
    echo.
    echo The tool may not work properly without FFmpeg.
    echo.
) else (
    echo FFmpeg found!
)

echo.
echo Installation completed!
echo.
echo You can now use the tool with:
echo   python main.py --help
echo.
echo For more information, see README.md
echo.
pause
