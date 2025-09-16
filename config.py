"""
Configuration settings for the Multi-Platform Music Downloader
"""

# Default settings
DEFAULT_OUTPUT_DIR = "downloads"
DEFAULT_AUDIO_QUALITY = 192  # kbps
DEFAULT_MAX_WORKERS = 8
DEFAULT_BATCH_SIZE = 50

# Audio format settings
SUPPORTED_AUDIO_FORMATS = ['mp3', 'm4a', 'wav', 'flac']
DEFAULT_AUDIO_FORMAT = 'mp3'

# Platform-specific settings
SOUNDCLOUD_SETTINGS = {
    'max_retries': 3,
    'timeout': 30,
    'quality': '192k',
}

YOUTUBE_SETTINGS = {
    'max_retries': 3,
    'timeout': 30,
    'quality': '192k',
    'max_duration': 3600,  # 1 hour in seconds
}

SPOTIFY_SETTINGS = {
    'max_retries': 2,
    'timeout': 20,
    'search_results': 10,
}

# Logging settings
LOG_LEVELS = {
    'DEBUG': 0,
    'INFO': 1,
    'WARNING': 2,
    'ERROR': 3,
}

# Error categories for analysis
ERROR_CATEGORIES = {
    'ACCESS_DENIED': 'Access denied or forbidden',
    'NOT_FOUND': 'Content not found or unavailable',
    'PRIVATE_CONTENT': 'Private or restricted content',
    'NETWORK_ISSUE': 'Network connectivity problems',
    'RATE_LIMITED': 'Rate limiting or too many requests',
    'GEO_BLOCKED': 'Geographic restrictions',
    'FORMAT_ISSUE': 'Audio format or codec problems',
    'STORAGE_ISSUE': 'Disk space or storage problems',
    'FILE_SYSTEM_ISSUE': 'File system errors',
    'UNKNOWN_ERROR': 'Uncategorized errors',
}

# File naming patterns
FILENAME_PATTERNS = {
    'track': '{title}',
    'playlist': '{title}',
    'with_artist': '{artist} - {title}',
    'numbered': '{number:02d} - {title}',
}

# Metadata fields
METADATA_FIELDS = ['title', 'artist', 'album', 'year', 'genre', 'track_number']

# Cover art settings
COVER_ART_SETTINGS = {
    'max_size': 1024,  # pixels
    'formats': ['jpg', 'png', 'webp'],
    'quality': 95,
}
