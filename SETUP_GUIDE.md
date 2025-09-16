# Complete Setup Guide for Multi-Platform Music Downloader

This guide will help you set up Python, pip, and all dependencies needed to run the music downloader project.

## 📋 Prerequisites

### Windows Setup

#### 1. Install Python

1. **Download Python**:

   - Go to [python.org](https://www.python.org/downloads/)
   - Click "Download Python 3.x.x" (latest version)
   - **IMPORTANT**: During installation, check "Add Python to PATH" at the bottom
   - Choose "Install Now"

2. **Verify Installation**:
   ```cmd
   python --version
   pip --version
   ```

#### 2. Install FFmpeg (Required for audio processing)

1. **Download FFmpeg**:

   - Go to [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
   - Click "Windows" → "Windows builds by BtbN"
   - Download the latest release (e.g., `ffmpeg-master-latest-win64-gpl.zip`)

2. **Install FFmpeg**:

   - Extract the zip file to `C:\ffmpeg`
   - Add `C:\ffmpeg\bin` to your Windows PATH:
     - Press `Win + R`, type `sysdm.cpl`, press Enter
     - Click "Environment Variables"
     - Under "System Variables", find and select "Path", click "Edit"
     - Click "New" and add: `C:\ffmpeg\bin`
     - Click OK on all dialogs

3. **Verify FFmpeg**:
   ```cmd
   ffmpeg -version
   ```

### macOS Setup

#### 1. Install Python

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python

# Verify installation
python3 --version
pip3 --version
```

#### 2. Install FFmpeg

```bash
brew install ffmpeg

# Verify installation
ffmpeg -version
```

### Linux Setup

#### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip python3-venv

# Install FFmpeg
sudo apt install ffmpeg

# Verify installation
python3 --version
pip3 --version
ffmpeg -version
```

#### CentOS/RHEL/Fedora

```bash
# For CentOS/RHEL 7/8
sudo yum install python3 python3-pip ffmpeg

# For CentOS/RHEL 9/Fedora
sudo dnf install python3 python3-pip ffmpeg

# Verify installation
python3 --version
pip3 --version
ffmpeg -version
```

## 🚀 Project Setup

### 1. Clone the Repository

```bash
git clone https://github.com/CilleIO/downloader-4-djs.git
cd downloader-4-djs
```

### 2. Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Windows (with virtual environment activated)
pip install -r requirements.txt

# macOS/Linux (with virtual environment activated)
pip3 install -r requirements.txt

# Alternative: Install without virtual environment
# Windows: pip install -r requirements.txt
# macOS/Linux: pip3 install -r requirements.txt
```

### 4. Set Up Environment Variables (Optional)

Create a `.env` file in the project root:

```bash
# Copy the example file
# Windows
copy env.example .env

# macOS/Linux
cp env.example .env
```

Edit `.env` with your credentials:

```
# Spotify API (optional)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret

# SoundCloud Authentication (optional)
SOUNDCLOUD_USERNAME=your_username
SOUNDCLOUD_PASSWORD=your_password
```

## ✅ Test Installation

### Quick Test

```bash
# Test basic functionality
python main.py --help

# Test YouTube download
python main.py youtube song "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Test with verbose logging
python main.py youtube song "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --verbose
```

### Expected Output

You should see:

- Help information for the first command
- Successful download for the test commands
- Files saved to the `downloads/` folder

## 🔧 Troubleshooting

### Common Issues

#### "python is not recognized"

**Solution**: Python is not in PATH

- Reinstall Python and check "Add Python to PATH"
- Or manually add Python to PATH

#### "pip is not recognized"

**Solution**: pip is not installed or not in PATH

```bash
# Try these alternatives
python -m pip --version
python3 -m pip --version
py -m pip --version
```

#### "ffmpeg is not recognized"

**Solution**: FFmpeg is not in PATH

- Make sure you added FFmpeg bin directory to PATH
- Restart your terminal/command prompt

#### "ModuleNotFoundError"

**Solution**: Dependencies not installed

```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

#### Permission Errors (Windows)

**Solution**: Run as Administrator or use virtual environment

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Getting Help

1. **Check Python Version**: Must be 3.8 or higher
2. **Check Internet Connection**: Required for downloading dependencies
3. **Try Virtual Environment**: Often resolves permission issues
4. **Check PATH Variables**: Both Python and FFmpeg must be accessible

## 📱 Platform-Specific Notes

### Windows Users

- Use `python` instead of `python3`
- Use `pip` instead of `pip3`
- Use backslashes in paths: `venv\Scripts\activate`

### macOS/Linux Users

- Use `python3` instead of `python`
- Use `pip3` instead of `pip`
- Use forward slashes in paths: `venv/bin/activate`

## 🎵 Ready to Use!

Once everything is set up, you can start downloading music:

```bash
# SoundCloud playlist
python main.py soundcloud playlist "https://soundcloud.com/user/sets/playlist"

# YouTube video
python main.py youtube song "https://www.youtube.com/watch?v=VIDEO_ID"

# Spotify playlist (requires API setup)
python main.py spotify playlist "https://open.spotify.com/playlist/PLAYLIST_ID"
```

Happy downloading! 🎧
