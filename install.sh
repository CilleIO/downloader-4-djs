#!/bin/bash

echo "Multi-Platform Music Downloader - Installation Script"
echo "====================================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ from your package manager or https://python.org"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed"
    echo "Please install pip3 from your package manager"
    exit 1
fi

echo "Installing Python dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo
echo "Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: FFmpeg not found in PATH"
    echo
    echo "FFmpeg is required for audio processing."
    echo "Please install FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  CentOS/RHEL:   sudo yum install ffmpeg"
    echo "  macOS:         brew install ffmpeg"
    echo
    echo "The tool may not work properly without FFmpeg."
    echo
else
    echo "FFmpeg found: $(ffmpeg -version | head -n 1)"
fi

echo
echo "Installation completed!"
echo
echo "You can now use the tool with:"
echo "  python3 main.py --help"
echo
echo "For more information, see README.md"
echo
