"""
Shared utilities for the multi-platform music downloader.
Contains common functions for logging, metadata handling, and file operations.
"""

import os
import re
import urllib.request
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# Global verbose logging flag
VERBOSE_LOGGING = False

def set_verbose_logging(enabled):
    """Set the global verbose logging flag"""
    global VERBOSE_LOGGING
    VERBOSE_LOGGING = enabled

def log(msg):
    """Log a general message"""
    print(f"[LOG] {msg}")

def log_error(msg):
    """Log an error message"""
    print(f"[ERROR] {msg}")

def log_debug(msg):
    """Log a debug message (only if verbose logging is enabled)"""
    if VERBOSE_LOGGING:
        print(f"[DEBUG] {msg}")

def log_warn(msg):
    """Log a warning message"""
    print(f"[WARN] {msg}")

def log_success(msg):
    """Log a success message"""
    print(f"[SUCCESS] {msg}")

def log_info(msg):
    """Log an info message"""
    print(f"[INFO] {msg}")

def sanitize_filename(filename):
    """Sanitize filename by removing invalid characters"""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def categorize_error(error_msg):
    """Categorize error messages to identify common failure patterns"""
    error_msg_lower = error_msg.lower()
    
    if any(keyword in error_msg_lower for keyword in ['403', 'forbidden', 'access denied']):
        return "ACCESS_DENIED"
    elif any(keyword in error_msg_lower for keyword in ['404', 'not found', 'unavailable']):
        return "NOT_FOUND"
    elif any(keyword in error_msg_lower for keyword in ['private', 'permission']):
        return "PRIVATE_CONTENT"
    elif any(keyword in error_msg_lower for keyword in ['timeout', 'connection', 'network']):
        return "NETWORK_ISSUE"
    elif any(keyword in error_msg_lower for keyword in ['rate limit', 'too many requests', '429']):
        return "RATE_LIMITED"
    elif any(keyword in error_msg_lower for keyword in ['geo', 'region', 'country']):
        return "GEO_BLOCKED"
    elif any(keyword in error_msg_lower for keyword in ['format', 'codec', 'ffmpeg']):
        return "FORMAT_ISSUE"
    elif any(keyword in error_msg_lower for keyword in ['disk', 'space', 'storage']):
        return "STORAGE_ISSUE"
    elif 'no such file' in error_msg_lower or 'file not found' in error_msg_lower:
        return "FILE_SYSTEM_ISSUE"
    else:
        return "UNKNOWN_ERROR"

def download_cover_art(url, output_path):
    """Download cover art from URL"""
    try:
        log_debug(f"Downloading cover art from: {url}")
        urllib.request.urlretrieve(url, output_path)
        return True
    except Exception as e:
        log_debug(f"Failed to download cover art: {e}")
        return False

def embed_metadata_and_cover(mp3_path, track_info, cover_art_path=None):
    """Embed metadata and cover art into MP3 file using mutagen"""
    if not MUTAGEN_AVAILABLE:
        log_debug("Mutagen not available, skipping metadata embedding")
        return False
    
    try:
        log_debug(f"Embedding metadata for: {mp3_path}")
        
        # Load the MP3 file
        audio_file = MP3(mp3_path, ID3=ID3)
        
        # Add ID3 tag if it doesn't exist
        try:
            audio_file.add_tags()
        except:
            pass  # Tags already exist
        
        # Set basic metadata
        if track_info.get('title'):
            audio_file["TIT2"] = TIT2(encoding=3, text=track_info['title'])
        
        if track_info.get('artist'):
            audio_file["TPE1"] = TPE1(encoding=3, text=track_info['artist'])
        
        if track_info.get('album'):
            audio_file["TALB"] = TALB(encoding=3, text=track_info['album'])
        
        # Embed cover art if available
        if cover_art_path and os.path.exists(cover_art_path):
            with open(cover_art_path, 'rb') as cover_file:
                cover_data = cover_file.read()
                
                # Determine MIME type based on file extension
                ext = os.path.splitext(cover_art_path)[1].lower()
                if ext == '.jpg' or ext == '.jpeg':
                    mime_type = 'image/jpeg'
                elif ext == '.png':
                    mime_type = 'image/png'
                elif ext == '.webp':
                    mime_type = 'image/webp'
                else:
                    mime_type = 'image/jpeg'  # Default
                
                audio_file["APIC"] = APIC(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=cover_data
                )
                log_debug(f"Embedded cover art: {cover_art_path}")
        
        # Save the file
        audio_file.save()
        log_debug(f"Successfully embedded metadata for: {mp3_path}")
        return True
        
    except Exception as e:
        log_debug(f"Failed to embed metadata for {mp3_path}: {e}")
        return False

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if seconds is None:
        return "Unknown"
    return str(timedelta(seconds=int(seconds)))

def ensure_directory(path):
    """Ensure directory exists, create if it doesn't"""
    os.makedirs(path, exist_ok=True)
    return path

def get_session_id():
    """Generate a unique session ID"""
    import os
    return os.urandom(4).hex()

def check_mutagen_availability():
    """Check if mutagen is available and warn if not"""
    if not MUTAGEN_AVAILABLE:
        log_warn("Mutagen not available - metadata enhancement will be limited. Install with: pip install mutagen")
        return False
    return True

def is_relevant_youtube_match(original_title, youtube_entry):
    """Check if a YouTube result is actually relevant to the original track"""
    yt_title = youtube_entry.get('title', '').lower()
    yt_uploader = youtube_entry.get('uploader', '').lower()
    original_lower = original_title.lower()
    
    # Extract key words from original title (ignore common words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'remix', 'edit', 'mix', 'feat', 'ft', 'featuring'}
    original_words = set(word.strip('()[]{}.,!?-_') for word in original_lower.split() if len(word) > 2 and word not in stop_words)
    yt_words = set(word.strip('()[]{}.,!?-_') for word in yt_title.split() if len(word) > 2)
    
    # Calculate word overlap
    common_words = original_words.intersection(yt_words)
    overlap_ratio = len(common_words) / max(len(original_words), 1)
    
    # Reject if no significant word overlap
    if overlap_ratio < 0.3:  # At least 30% word overlap
        log_debug(f"Low word overlap ({overlap_ratio:.2f}): '{original_title}' vs '{yt_title}'")
        return False
    
    # Reject obvious false matches
    false_match_indicators = [
        'tutorial', 'lesson', 'how to', 'reaction', 'review', 'interview', 
        'documentary', 'live stream', 'podcast', 'news', 'trailer', 'teaser',
        'behind the scenes', 'making of', 'compilation', 'festival', 'concert'
    ]
    
    for indicator in false_match_indicators:
        if indicator in yt_title or indicator in yt_uploader:
            log_debug(f"Rejected due to false match indicator '{indicator}': {yt_title}")
            return False
    
    # Additional validation: duration shouldn't be too long (likely a mix/set)
    duration = youtube_entry.get('duration', 0)
    if duration > 600:  # 10 minutes - likely a DJ set or mix
        log_debug(f"Rejected due to excessive duration ({duration}s): {yt_title}")
        return False
    
    log_debug(f"Accepted match (overlap: {overlap_ratio:.2f}): '{original_title}' -> '{yt_title}'")
    return True

def analyze_failures(failed_tracks):
    """Analyze and categorize failed tracks"""
    if not failed_tracks:
        return
    
    log(f"\n=== FAILURE ANALYSIS ===")
    
    # Categorize errors
    error_categories = {}
    for track in failed_tracks:
        category = categorize_error(track['reason'])
        if category not in error_categories:
            error_categories[category] = []
        error_categories[category].append(track)
    
    # Show categorized failures
    for category, tracks in error_categories.items():
        log(f"{category}: {len(tracks)} tracks")
        for t in tracks:
            log_error(f"  - {t['title']} | {t['url']} | {t['reason']}")
    
    # Show overall failure breakdown
    log(f"\n=== FAILURE BREAKDOWN ===")
    for category, tracks in sorted(error_categories.items(), key=lambda x: len(x[1]), reverse=True):
        percentage = (len(tracks) / len(failed_tracks)) * 100
        log(f"{category}: {len(tracks)} tracks ({percentage:.1f}%)")

def write_failed_tracks_file(failed_tracks, output_path):
    """Write failed tracks to a text file"""
    if failed_tracks:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("Tracks that failed to download:\n\n")
            for t in failed_tracks:
                f.write(f"Title: {t['title']}\nURL: {t['url']}\nReason: {t['reason']}\n\n")
        return output_path
    return None

def check_file_exists_in_folder(folder_path, filename_pattern):
    """Check if a file with similar name already exists in the folder"""
    if not os.path.exists(folder_path):
        return None
    
    # Remove extension from pattern
    base_pattern = filename_pattern.rsplit('.', 1)[0] if '.' in filename_pattern else filename_pattern
    
    for file in os.listdir(folder_path):
        if file.endswith(('.mp3', '.m4a', '.wav', '.flac', '.webm', '.ogg')):
            file_base = file.rsplit('.', 1)[0]
            # Check if the base names are similar (accounting for slight variations)
            if base_pattern.lower() in file_base.lower() or file_base.lower() in base_pattern.lower():
                return os.path.join(folder_path, file)
    return None

def generate_unique_filename(folder_path, desired_filename):
    """Generate a unique filename if the desired one already exists"""
    if not os.path.exists(os.path.join(folder_path, desired_filename)):
        return desired_filename
    
    base_name, ext = os.path.splitext(desired_filename)
    counter = 1
    while True:
        new_filename = f"{base_name}_{counter}{ext}"
        if not os.path.exists(os.path.join(folder_path, new_filename)):
            return new_filename
        counter += 1
