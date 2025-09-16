# Multi-Platform Music Downloader

A comprehensive, open-source tool for DJs and music enthusiasts to download music from multiple platforms including SoundCloud, Spotify, and YouTube. This tool handles both single tracks and complete playlists with intelligent fallback mechanisms and extensive debugging capabilities.

## 🎵 Features

- **Multi-Platform Support**: Download from SoundCloud, Spotify, and YouTube
- **Smart Fallback**: Automatic YouTube search when direct downloads fail
- **Playlist Support**: Download entire playlists with progress tracking
- **Metadata Enhancement**: Automatic embedding of track metadata and cover art
- **Concurrent Downloads**: Fast parallel processing for large playlists
- **Extensive Logging**: Detailed progress tracking and error analysis
- **Error Recovery**: Multiple retry strategies and failure categorization
- **DJ-Friendly**: Optimized for DJ use with quality audio output

## 🚀 Quick Start

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/CilleIO/downloader-4-djs.git
   cd downloader-4-djs
   ```

2. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (required for audio processing):
   - **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (CentOS/RHEL)

### Basic Usage

```bash
# Download a SoundCloud playlist
python main.py soundcloud playlist "https://soundcloud.com/user/sets/playlist-name"

# Download a single YouTube track
python main.py youtube song "https://www.youtube.com/watch?v=VIDEO_ID"

# Download with verbose logging
python main.py soundcloud playlist "URL" --verbose

# Custom output filename
python main.py youtube playlist "URL" --output "my_mix_2024"
```

## 📖 Detailed Usage

### Command Line Interface

```bash
python main.py <platform> <type> <url> [options]
```

#### Platforms

- `soundcloud` - SoundCloud tracks and playlists
- `spotify` - Spotify tracks and playlists (with YouTube fallback)
- `youtube` - YouTube videos and playlists

#### Content Types

- `song` - Single track download
- `playlist` - Complete playlist download

#### Options

- `--verbose, -v` - Enable detailed logging for debugging
- `--output, -o` - Specify custom folder name for playlist downloads
- `--manual` - For Spotify: manually enter track information

### Examples

#### SoundCloud Downloads

```bash
# Download a SoundCloud playlist
python main.py soundcloud playlist "https://soundcloud.com/dj-name/sets/mix-name"

# Download a single SoundCloud track
python main.py soundcloud song "https://soundcloud.com/artist/track-name"

# Download with custom name and verbose logging
python main.py soundcloud playlist "URL" --output "summer_mix_2024" --verbose
```

#### YouTube Downloads

```bash
# Download a YouTube playlist
python main.py youtube playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Download a single YouTube video
python main.py youtube song "https://www.youtube.com/watch?v=VIDEO_ID"

# Download with verbose logging
python main.py youtube playlist "URL" --verbose
```

#### Spotify Downloads

```bash
# Manual track entry (recommended for Spotify)
python main.py spotify song --manual

# The tool will prompt you to enter track information manually
# It will then search YouTube for each track
```

### Legacy Mode (Auto-Detection)

The tool also supports legacy mode where it auto-detects the platform and content type:

```bash
# Auto-detect platform and type from URL
python main.py "https://soundcloud.com/user/sets/playlist-name"

# With verbose logging
python main.py "URL" --verbose
```

## 🏗️ Project Structure

```
downloader-4-djs/
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── config.py              # Configuration settings
├── downloads/             # Downloaded content (ignored by git)
│   ├── .gitkeep          # Ensures folder is tracked
│   └── README.md         # Folder documentation
├── shared/                # Shared utilities
│   ├── __init__.py
│   └── utils.py           # Common functions, logging, metadata
├── soundcloud/            # SoundCloud downloader
│   ├── __init__.py
│   └── downloader.py      # SoundCloud-specific logic
├── spotify/               # Spotify downloader
│   ├── __init__.py
│   └── downloader.py      # Spotify-specific logic
└── youtube/               # YouTube downloader
    ├── __init__.py
    └── downloader.py      # YouTube-specific logic
```

## 🔧 Advanced Features

### Intelligent Fallback System

When a track fails to download from the original platform, the tool automatically:

1. **Retries with different settings** (quality, format, headers)
2. **Searches YouTube** for the same track
3. **Validates matches** using intelligent title matching
4. **Reports detailed failure analysis** with categorized error types

### Metadata Enhancement

The tool automatically:

- Embeds track metadata (title, artist, album)
- Downloads and embeds cover art
- Uses high-quality audio formats (192kbps MP3)
- Handles various image formats (JPG, PNG, WebP)

### Concurrent Processing

- **Parallel downloads** for faster playlist processing
- **Adaptive concurrency** based on playlist size
- **Batch processing** for metadata extraction
- **Progress tracking** with detailed logging

### Error Handling

- **Comprehensive error categorization** (network, permissions, format issues)
- **Multiple retry strategies** with progressive backoff
- **Detailed failure reports** in FAILED_DOWNLOADS.txt
- **Recovery statistics** showing success rates

## 🐛 Troubleshooting

### Common Issues

#### FFmpeg Not Found

```
Error: FFmpeg not found
```

**Solution**: Install FFmpeg and ensure it's in your system PATH.

#### Permission Errors

```
Error: Access denied / 403 Forbidden
```

**Solution**: Some tracks may be private or region-locked. The tool will attempt YouTube fallback.

#### Network Timeouts

```
Error: Connection timeout
```

**Solution**: The tool includes automatic retries with progressive backoff.

#### Missing Dependencies

```
Error: Module not found
```

**Solution**: Run `pip install -r requirements.txt` to install all dependencies.

### Debug Mode

Enable verbose logging to see detailed information:

```bash
python main.py soundcloud playlist "URL" --verbose
```

This will show:

- Detailed download progress
- Network requests and responses
- Error messages and stack traces
- Metadata processing steps

### Output Organization

The tool organizes downloads as follows:

- **Single tracks**: Downloaded directly to the `downloads/` folder
- **Playlists**: Downloaded to subfolders with session-specific names:
  - `downloads/SoundCloud_Playlist_[session_id]/`
  - `downloads/Spotify_Manual_Tracks_[session_id]/`
  - `downloads/YouTube_Playlist_[session_id]/`
- **FAILED_DOWNLOADS.txt**: Created in each playlist folder with details of failed tracks
- **No ZIP files**: All content is organized in folders for easy access

## 🔒 Legal Notice

This tool is provided for educational and personal use only. Users are responsible for:

- **Respecting copyright laws** in their jurisdiction
- **Obtaining proper licenses** for commercial use
- **Complying with platform terms of service**
- **Using downloaded content legally**

The developers are not responsible for any misuse of this tool.

## 🤝 Contributing

We welcome contributions from the DJ community! Please:

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Add tests if applicable**
5. **Submit a pull request**

### Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/CilleIO/downloader-4-djs.git
cd downloader-4-djs
pip install -r requirements.txt

# Run tests (when available)
python -m pytest tests/

# Format code
black .
```

## 📋 Roadmap

- [ ] **Spotify Web API Integration** for direct playlist extraction
- [ ] **GUI Interface** for non-technical users
- [ ] **Batch Processing** for multiple playlists
- [ ] **Audio Quality Options** (320kbps, FLAC)
- [ ] **Custom Output Formats** (WAV, M4A)
- [ ] **Playlist Metadata** (description, artwork)
- [ ] **Progress Bars** for better user experience
- [ ] **Configuration Files** for default settings

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **yt-dlp** for excellent video/audio extraction capabilities
- **mutagen** for audio metadata handling
- **The DJ community** for feedback and feature requests

## 📞 Support

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/CilleIO/downloader-4-djs/issues)
- **Discussions**: Join community discussions on [GitHub Discussions](https://github.com/CilleIO/downloader-4-djs/discussions)
- **Documentation**: Check the wiki for detailed guides

---

**Made with ❤️ for the DJ community**

_Happy mixing! 🎧_
