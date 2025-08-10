import yt_dlp
import os
import sys
import zipfile
import shutil
import json
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


def enhance_track_metadata(mp3_path, original_url):
    """Enhance track metadata by fetching additional info from SoundCloud"""
    try:
        log_debug(f"Enhancing metadata for: {mp3_path}")
        
        # Get track info from original URL
        track_info = get_track_info(original_url)
        if not track_info:
            log_debug(f"Could not fetch track info for metadata enhancement: {original_url}")
            return False
        
        # Download cover art if available
        cover_art_path = None
        if track_info.get('thumbnail'):
            cover_ext = '.jpg'
            if '.webp' in track_info['thumbnail']:
                cover_ext = '.webp'
            elif '.png' in track_info['thumbnail']:
                cover_ext = '.png'
            
            cover_art_path = mp3_path.replace('.mp3', f'_cover{cover_ext}')
            if download_cover_art(track_info['thumbnail'], cover_art_path):
                log_debug(f"Downloaded cover art: {cover_art_path}")
            else:
                cover_art_path = None
        
        # Prepare metadata dict
        metadata = {
            'title': track_info.get('title', ''),
            'artist': track_info.get('artist') or track_info.get('uploader') or track_info.get('creator') or '',
            'album': track_info.get('album') or track_info.get('playlist_title') or 'SoundCloud'
        }
        
        # Embed metadata and cover art
        success = embed_metadata_and_cover(mp3_path, metadata, cover_art_path)
        
        # Clean up temporary cover art file
        if cover_art_path and os.path.exists(cover_art_path):
            try:
                os.remove(cover_art_path)
                log_debug(f"Cleaned up temporary cover art: {cover_art_path}")
            except:
                pass
        
        return success
        
    except Exception as e:
        log_debug(f"Error enhancing metadata for {mp3_path}: {e}")
        return False


def check_and_enhance_all_metadata(file_paths, track_urls_map):
    """Check all downloaded files and enhance metadata for those missing it"""
    log("=== METADATA ENHANCEMENT PHASE ===")
    
    enhanced_count = 0
    files_to_enhance = []
    
    # Check which files need metadata enhancement
    for file_path in file_paths:
        if not file_path.endswith('.mp3'):
            continue
            
        needs_enhancement = False
        
        if MUTAGEN_AVAILABLE:
            try:
                audio_file = MP3(file_path, ID3=ID3)
                
                # Check if basic metadata exists
                has_title = "TIT2" in audio_file
                has_artist = "TPE1" in audio_file
                has_cover = "APIC:Cover" in audio_file or any(key.startswith("APIC") for key in audio_file.keys())
                
                if not (has_title and has_artist and has_cover):
                    needs_enhancement = True
                    log_debug(f"File needs enhancement - Title: {has_title}, Artist: {has_artist}, Cover: {has_cover}")
                    
            except Exception as e:
                log_debug(f"Error checking metadata for {file_path}: {e}")
                needs_enhancement = True
        else:
            # Without mutagen, assume all files need enhancement
            needs_enhancement = True
        
        if needs_enhancement:
            files_to_enhance.append(file_path)
    
    if not files_to_enhance:
        log("All files already have complete metadata!")
        return enhanced_count
    
    log(f"Enhancing metadata for {len(files_to_enhance)} files...")
    
    # Find corresponding URLs for files that need enhancement
    with ThreadPoolExecutor(max_workers=4) as executor:  # Limit concurrent metadata downloads
        enhancement_futures = []
        
        for file_path in files_to_enhance:
            # Try to find the original URL for this file
            original_url = None
            filename = os.path.basename(file_path)
            
            # Look for matching URL based on filename
            for url, info in track_urls_map.items():
                if info and 'title' in info:
                    title = sanitize_filename(info['title'])
                    if title in filename or filename.startswith(title):
                        original_url = url
                        break
            
            if original_url:
                log_debug(f"Found matching URL for {filename}: {original_url}")
                future = executor.submit(enhance_track_metadata, file_path, original_url)
                enhancement_futures.append((future, file_path))
            else:
                log_debug(f"Could not find matching URL for: {filename}")
        
        # Process enhancement results
        for future, file_path in enhancement_futures:
            try:
                success = future.result()
                if success:
                    enhanced_count += 1
                    log(f"✓ Enhanced metadata: {os.path.basename(file_path)}")
                else:
                    log_debug(f"✗ Failed to enhance metadata: {os.path.basename(file_path)}")
            except Exception as e:
                log_debug(f"✗ Enhancement error for {file_path}: {e}")
    
    log(f"Metadata enhancement completed: {enhanced_count}/{len(files_to_enhance)} files enhanced")
    return enhanced_count

def log(msg):
    print(f"[LOG] {msg}")

def log_error(msg):
    print(f"[ERROR] {msg}")

def log_debug(msg):
    if VERBOSE_LOGGING:
        print(f"[DEBUG] {msg}")

def log_warn(msg):
    print(f"[WARN] {msg}")

# Check if mutagen is available and warn if not
if not MUTAGEN_AVAILABLE:
    log_warn("Mutagen not available - metadata enhancement will be limited. Install with: pip install mutagen")

def sanitize_filename(filename):
    import re
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def extract_soundcloud_tracks(playlist_url, max_retries=3):
    """Extract tracks from playlist with retry logic for large playlists"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': True,
        'force_generic_extractor': False,
        'socket_timeout': 30,  # 30 second timeout
        'retries': 5,
        'fragment_retries': 5,
    }
    
    for attempt in range(max_retries):
        try:
            log_debug(f"Extracting playlist (attempt {attempt + 1}/{max_retries})")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                if not info:
                    log_warn(f"No playlist info returned on attempt {attempt + 1}")
                    continue
                    
                if isinstance(info, dict):
                    if 'entries' in info:
                        tracks = [entry['url'] for entry in info['entries'] if isinstance(entry, dict) and 'url' in entry]
                        log_debug(f"Successfully extracted {len(tracks)} tracks")
                        return tracks
                    if 'url' in info:
                        return [info['url']]
        except Exception as e:
            log_warn(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 5  # Progressive backoff: 5s, 10s, 15s
                log(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                log_error(f"All {max_retries} attempts failed to extract playlist")
    
    return []

def get_track_info(url, max_retries=2):
    """Get track info with timeout and retry logic"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'socket_timeout': 15,  # Shorter timeout for individual tracks
        'retries': 2,
    }
    
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            if attempt < max_retries - 1:
                log_debug(f"Track info retry for {url}: {e}")
                import time
                time.sleep(2)  # Short wait
            else:
                log_debug(f"Failed to get track info after {max_retries} attempts: {url}")
    
    return None

def download_track(url, output_folder, verbose=False):
    """Download a track with enhanced error logging"""
    log_debug(f"Starting download_track for: {url}")
    
    info = get_track_info(url)
    if not info:
        log_error(f"Failed to extract track info for: {url}")
        return None, None, None, None, None
        
    title = info.get('title', 'unknown_track')
    duration = info.get('duration', 0)
    artist = info.get('artist') or info.get('uploader') or info.get('creator') or ''
    
    log_debug(f"Track info - Title: '{title}', Artist: '{artist}', Duration: {duration}s")
    
    # Output template: just the title (no numbering, no artist)
    output_template = os.path.join(output_folder, f"%(title)s.%(ext)s")
    
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'bestaudio/best',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata',
            },
            {
                'key': 'EmbedThumbnail',
            },
        ],
        'addmetadata': True,
        'writethumbnail': True,
        'embedthumbnail': True,
        'quiet': not verbose,  # Enable verbose output if requested
        'no_warnings': not verbose,
        'ignoreerrors': True,
        'socket_timeout': 30,  # 30 second timeout for downloads
        'retries': 3,
        'fragment_retries': 3,
    }
    
    # Add error capture
    class DownloadErrorHandler:
        def __init__(self):
            self.errors = []
            self.warnings = []
        
        def debug(self, msg):
            if verbose:
                log_debug(f"yt-dlp: {msg}")
        
        def warning(self, msg):
            self.warnings.append(msg)
            log_warn(f"yt-dlp warning: {msg}")
        
        def error(self, msg):
            self.errors.append(msg)
            log_error(f"yt-dlp error: {msg}")
    
    error_handler = DownloadErrorHandler()
    ydl_opts['logger'] = error_handler
    
    try:
        log_debug(f"Starting yt-dlp download for: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        log_debug(f"yt-dlp download completed for: {title}")
    except Exception as e:
        log_error(f"yt-dlp download exception for '{title}': {e}")
        if error_handler.errors:
            log_error(f"yt-dlp errors: {'; '.join(error_handler.errors)}")
        if error_handler.warnings:
            log_warn(f"yt-dlp warnings: {'; '.join(error_handler.warnings)}")
        return None, title, duration, artist, None
    
    # Check for download success
    base_filename = f"{title}.mp3"
    output_path = os.path.join(output_folder, base_filename)
    
    if not os.path.exists(output_path):
        log_debug(f"Expected file not found: {output_path}")
        log_debug(f"Searching for similar files in: {output_folder}")
        
        # Look for any file with similar name
        found_file = None
        for file in os.listdir(output_folder):
            if file.endswith('.mp3') and title in file:
                found_file = os.path.join(output_folder, file)
                log_debug(f"Found similar file: {file}")
                break
        
        if found_file:
            output_path = found_file
        else:
            log_error(f"No output file found for '{title}' after download")
            log_debug(f"Files in download folder: {os.listdir(output_folder)}")
            if error_handler.errors:
                log_error(f"Download errors: {'; '.join(error_handler.errors)}")
            if error_handler.warnings:
                log_warn(f"Download warnings: {'; '.join(error_handler.warnings)}")
            return None, title, duration, artist, None
    
    # Look for cover art
    cover_art = None
    for ext in ['jpg', 'webp', 'png']:
        thumb_path = os.path.join(output_folder, f"{title}.{ext}")
        if os.path.exists(thumb_path):
            cover_art = thumb_path
            log_debug(f"Found cover art: {thumb_path}")
            break
    
    log_debug(f"Successfully downloaded: {output_path}")
    return output_path, title, duration, artist, cover_art

def search_youtube_for_longer_version(title, min_duration=31):
    """Search YouTube for a longer version with improved matching"""
    query = f"ytsearch10:{title}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'socket_timeout': 20,
        'retries': 2,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(query, download=False)
        if 'entries' in results:
            for entry in results['entries']:
                if entry and entry.get('duration', 0) >= min_duration:
                    # Validate that this is actually a relevant match
                    if is_relevant_youtube_match(title, entry):
                        log_debug(f"Found relevant YouTube match: {entry['title']}")
                        return entry['webpage_url'], entry['duration']
                    else:
                        log_debug(f"Rejected irrelevant match: {entry['title']}")
    return None, None


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

def process_track(idx, track_url, total_tracks, download_folder, failed_tracks):
    try:
        log(f"[{idx}/{total_tracks}] Downloading track: {track_url}")
        sc_file, title, duration, artist, cover_art = download_track(track_url, download_folder, verbose=VERBOSE_LOGGING)
        if sc_file and duration is not None:
            if os.path.exists(sc_file):
                log(f"Downloaded '{title}' by '{artist}' ({str(timedelta(seconds=duration))})")
                if duration <= 30:
                    log(f"Track '{title}' is {duration}s (<=30s). Searching YouTube for longer version...")
                    yt_url, yt_duration = search_youtube_for_longer_version(title)
                    if yt_url:
                        log(f"Found YouTube version: {yt_url} ({yt_duration}s). Downloading...")
                        yt_file, yt_title, yt_dur, yt_artist, yt_cover = download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                        if yt_file and yt_dur > duration and os.path.exists(yt_file):
                            log(f"Replaced with YouTube version: '{yt_title}' by '{yt_artist}' ({str(timedelta(seconds=yt_dur))})")
                            try:
                                os.remove(sc_file)
                            except Exception as e:
                                log(f"Failed to remove short SC file: {e}")
                            return yt_file
                        elif yt_file and not os.path.exists(yt_file):
                            failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                            log(f"[WARN] YouTube download reported success but file missing: {yt_file}")
                        else:
                            log(f"YouTube version not found or not longer. Keeping original.")
                    else:
                        log(f"No suitable YouTube version found. Keeping original.")
                return sc_file
            else:
                failed_tracks.append({'title': title, 'url': track_url, 'reason': 'yt_dlp reported success but file missing (possible duplicate title or yt_dlp error)'})
                log(f"[WARN] yt_dlp reported success but file missing: {sc_file}")
                # Try YouTube fallback for missing file
                yt_url, yt_duration = search_youtube_for_longer_version(title)
                if yt_url:
                    log(f"Trying YouTube fallback for '{title}': {yt_url}")
                    yt_file, yt_title, yt_dur, yt_artist, yt_cover = download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                    if yt_file and os.path.exists(yt_file):
                        log(f"Successfully downloaded from YouTube: '{yt_title}' by '{yt_artist}'")
                        return yt_file
                    elif yt_file and not os.path.exists(yt_file):
                        failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                        log(f"[WARN] YouTube download reported success but file missing: {yt_file}")
                    else:
                        log(f"Failed to download from YouTube: {yt_url}")
                        failed_tracks.append({'title': title, 'url': yt_url, 'reason': 'Failed on SoundCloud (file missing) and YouTube download'})
                else:
                    failed_tracks.append({'title': title, 'url': track_url, 'reason': 'Failed on SoundCloud (file missing), no suitable YouTube match'})
                return None
        else:
            log(f"Failed to download track from SoundCloud: {track_url}")
            # Try YouTube fallback
            info = get_track_info(track_url)
            title = info.get('title', 'unknown_track') if info else track_url
            yt_url, yt_duration = search_youtube_for_longer_version(title)
            if yt_url:
                log(f"Trying YouTube fallback for '{title}': {yt_url}")
                yt_file, yt_title, yt_dur, yt_artist, yt_cover = download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                if yt_file and os.path.exists(yt_file):
                    log(f"Successfully downloaded from YouTube: '{yt_title}' by '{yt_artist}'")
                    return yt_file
                elif yt_file and not os.path.exists(yt_file):
                    failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                    log(f"[WARN] YouTube download reported success but file missing: {yt_file}")
                else:
                    log(f"Failed to download from YouTube: {yt_url}")
                    failed_tracks.append({'title': title, 'url': yt_url, 'reason': 'Failed on SoundCloud and YouTube download'})
            else:
                failed_tracks.append({'title': title, 'url': track_url, 'reason': 'Failed on SoundCloud, no suitable YouTube match'})
            return None
    except Exception as e:
        log(f"Error processing track {track_url}: {e}")
        failed_tracks.append({'title': track_url, 'url': track_url, 'reason': f'Exception: {e}'})
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <soundcloud_playlist_url> [--verbose]")
        print("  --verbose: Enable detailed logging for debugging download issues")
        sys.exit(1)
    
    playlist_url = sys.argv[1]
    verbose_mode = '--verbose' in sys.argv or '-v' in sys.argv
    
    if verbose_mode:
        log("Verbose mode enabled - detailed logging will be shown")
        global VERBOSE_LOGGING
        VERBOSE_LOGGING = True
    
    # Prompt for zip file name
    zip_filename = input("Enter a name for the output zip file (without .zip, leave blank for default): ").strip()
    if zip_filename:
        if not zip_filename.lower().endswith('.zip'):
            zip_filename += '.zip'
    
    session_id = os.urandom(4).hex()
    if not zip_filename:
        zip_filename = f"soundcloud_playlist_{session_id}.zip"
    
    # Ensure downloads directory exists
    downloads_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    
    log(f"Extracting tracks from playlist: {playlist_url}")
    track_urls = extract_soundcloud_tracks(playlist_url)
    original_track_count = len(track_urls)
    log(f"Found {original_track_count} tracks in playlist.")
    
    # Exit early if no tracks found
    if original_track_count == 0:
        log_error("No tracks found. The playlist might be private or the URL might be invalid.")
        return
    
    download_folder = os.path.join(downloads_dir, f"sc_dl_{session_id}")
    os.makedirs(download_folder, exist_ok=True)
    
    final_files = []
    failed_tracks = []
    successful_track_urls = []  # Track which URLs were successfully downloaded
    track_url_info_map = {}  # Map URLs to their track info for metadata enhancement
    
    # Pre-fetch track info for metadata enhancement later (in batches for large playlists)
    log("Pre-fetching track information for metadata enhancement...")
    
    def process_info_batch(batch_urls):
        """Process a batch of URLs for track info"""
        batch_results = {}
        for url in batch_urls:
            try:
                info = get_track_info(url)
                if info:
                    batch_results[url] = info
                    log_debug(f"Cached info for: {info.get('title', 'Unknown')}")
                else:
                    batch_results[url] = None
            except Exception as e:
                log_debug(f"Failed to cache info for {url}: {e}")
                batch_results[url] = None
        return batch_results
    
    # Process in batches of 50 to avoid overwhelming the network
    batch_size = 50
    total_batches = (len(track_urls) + batch_size - 1) // batch_size
    
    with ThreadPoolExecutor(max_workers=3) as info_executor:  # Limit concurrent info requests
        info_futures = []
        
        for i in range(0, len(track_urls), batch_size):
            batch = track_urls[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            log(f"Processing info batch {batch_num}/{total_batches} ({len(batch)} tracks)")
            
            future = info_executor.submit(process_info_batch, batch)
            info_futures.append(future)
        
        # Collect results
        for future in as_completed(info_futures):
            try:
                batch_results = future.result()
                track_url_info_map.update(batch_results)
            except Exception as e:
                log_error(f"Batch info processing failed: {e}")
    
    log(f"Cached info for {len([v for v in track_url_info_map.values() if v])} tracks")
    
    # Adjust concurrency for large playlists
    if original_track_count > 200:
        max_workers = min(6, max(1, len(track_urls)))  # Reduce workers for large playlists
        log(f"Large playlist detected ({original_track_count} tracks), reducing concurrency to {max_workers} workers")
    else:
        max_workers = min(8, max(1, len(track_urls)))
    
    from functools import partial
    
    # Initial download attempt
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(process_track, idx, url, len(track_urls), download_folder, failed_tracks): url
            for idx, url in enumerate(track_urls, 1)
        }
        
        for future in as_completed(future_to_url):
            result = future.result()
            if result and os.path.exists(result):
                final_files.append(result)
                successful_track_urls.append(future_to_url[future])  # Track successful URL
            elif result:
                log(f"[WARN] File not found after download: {result}")
    
    # Cross-reference: Find missing tracks
    log(f"\n=== CROSS-REFERENCING DOWNLOADS ===")
    log(f"Original tracks to download: {original_track_count}")
    log(f"Successfully downloaded: {len(final_files)}")
    
    if len(final_files) < original_track_count:
        missing_count = original_track_count - len(final_files)
        log(f"Missing tracks: {missing_count}")
        
        # Find missing tracks by comparing URLs (more reliable than file names)
        successful_urls_set = set(successful_track_urls)
        missing_track_urls = [url for url in track_urls if url not in successful_urls_set]
        
        # Get track information for missing URLs
        missing_tracks = []
        for idx, url in enumerate(missing_track_urls, 1):
            try:
                info = get_track_info(url)
                if info:
                    missing_tracks.append({
                        'title': info.get('title', f'unknown_track_{idx}'),
                        'url': url,
                        'artist': info.get('artist') or info.get('uploader') or info.get('creator') or 'Unknown',
                        'idx': idx
                    })
                else:
                    missing_tracks.append({
                        'title': f'unknown_track_{idx}',
                        'url': url,
                        'artist': 'Unknown',
                        'idx': idx
                    })
            except Exception as e:
                log(f"Error getting info for track {url}: {e}")
                missing_tracks.append({
                    'title': f'error_track_{idx}',
                    'url': url,
                    'artist': 'Unknown',
                    'idx': idx
                })
        
        if missing_tracks:
            log(f"Identified {len(missing_tracks)} missing tracks. Attempting SoundCloud retry first...")
            
            # First attempt: Retry SoundCloud downloads with different settings
            recovery_files = []
            soundcloud_retry_failed = []
            
            log("=== SOUNDCLOUD RETRY PHASE ===")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                sc_retry_futures = []
                for track in missing_tracks:
                    log(f"Retrying SoundCloud download for: '{track['title']}' by '{track['artist']}'")
                    future = executor.submit(retry_soundcloud_download, track, download_folder)
                    sc_retry_futures.append((future, track))
                
                for future, track in sc_retry_futures:
                    try:
                        result = future.result()
                        if result and os.path.exists(result):
                            recovery_files.append(result)
                            log(f"✓ SoundCloud retry successful: '{track['title']}'")
                        else:
                            soundcloud_retry_failed.append(track)
                            log(f"✗ SoundCloud retry failed: '{track['title']}'")
                    except Exception as e:
                        log(f"SoundCloud retry error for '{track['title']}': {e}")
                        soundcloud_retry_failed.append(track)
            
            log(f"SoundCloud retry phase: {len(recovery_files)} recovered, {len(soundcloud_retry_failed)} still missing")
            
            # Second attempt: YouTube fallback for tracks that still failed SoundCloud retry
            if soundcloud_retry_failed:
                log("=== YOUTUBE FALLBACK PHASE ===")
                log(f"Attempting YouTube fallback for {len(soundcloud_retry_failed)} remaining tracks...")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    yt_recovery_futures = []
                    for track in soundcloud_retry_failed:
                        log(f"Searching YouTube for: '{track['title']}' by '{track['artist']}'")
                        
                        # Enhanced search queries
                        search_queries = [
                            f"{track['title']} {track['artist']}",
                            track['title'],
                            f"{track['artist']} {track['title']}",
                            f"{track['title']} official",
                            f"{track['title']} audio"
                        ]
                        
                        for query in search_queries:
                            future = executor.submit(attempt_youtube_recovery, query, track, download_folder)
                            yt_recovery_futures.append((future, track))
                            break  # Try first query, if it fails we'll try others
                    
                    for future, track in yt_recovery_futures:
                        try:
                            result = future.result()
                            if result and os.path.exists(result):
                                recovery_files.append(result)
                                log(f"✓ YouTube recovery successful: '{track['title']}'")
                            else:
                                # Try additional search queries if first failed
                                yt_recovered = False
                                for query in [f"{track['title']} official", f"{track['title']} audio", track['title']]:
                                    result = attempt_youtube_recovery(query, track, download_folder)
                                    if result and os.path.exists(result):
                                        recovery_files.append(result)
                                        log(f"✓ YouTube recovery successful with alternate search: '{track['title']}'")
                                        yt_recovered = True
                                        break
                                
                                if not yt_recovered:
                                    log(f"✗ Complete failure: '{track['title']}'")
                                    failed_tracks.append({
                                        'title': track['title'], 
                                        'url': track['url'], 
                                        'reason': 'Failed SoundCloud retry and YouTube fallback after cross-referencing'
                                    })
                        except Exception as e:
                            log(f"YouTube recovery error for '{track['title']}': {e}")
                            failed_tracks.append({
                                'title': track['title'], 
                                'url': track['url'], 
                                'reason': f'SoundCloud retry failed, YouTube recovery exception: {e}'
                            })
            
            # Add all recovered files to final files
            final_files.extend(recovery_files)
            log(f"=== RECOVERY SUMMARY ===")
            log(f"Total recovered tracks: {len(recovery_files)}")
            log(f"SoundCloud retries successful: {len(recovery_files) - len([f for f in recovery_files if 'youtube' in str(f).lower()])}")
            log(f"YouTube fallbacks successful: {len([f for f in recovery_files if 'youtube' in str(f).lower()])}")
            log(f"Complete failures: {len(failed_tracks)}")
    
    # Metadata enhancement phase
    mp3_files = [f for f in final_files if f.endswith('.mp3')]
    enhanced_count = 0
    if mp3_files:
        enhanced_count = check_and_enhance_all_metadata(mp3_files, track_url_info_map)
        log(f"Enhanced metadata for {enhanced_count} files")
    
    # Final summary
    log(f"\n=== FINAL SUMMARY ===")
    log(f"Original tracks: {original_track_count}")
    log(f"Successfully downloaded: {len(mp3_files)}")
    log(f"Enhanced with metadata: {enhanced_count}")
    log(f"Failed tracks: {len(failed_tracks)}")
    
    # Write failed tracks to a text file
    failed_txt_path = os.path.join(download_folder, "FAILED_DOWNLOADS.txt")
    if failed_tracks:
        with open(failed_txt_path, "w", encoding="utf-8") as f:
            f.write("Tracks that failed to download:\n\n")
            for t in failed_tracks:
                f.write(f"Title: {t['title']}\nURL: {t['url']}\nReason: {t['reason']}\n\n")
        final_files.append(failed_txt_path)
    
    # Zip the results
    zip_path = os.path.join(downloads_dir, zip_filename)
    log(f"Zipping {len(final_files)} files to {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in final_files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname=arcname)
                log(f"Added to zip: {arcname}")
            else:
                log(f"[WARN] Skipping missing file during zipping: {file_path}")
    
    log(f"Done! Playlist zip created at: {zip_path}")
    
    # Print summary of failed tracks with error categorization
    if failed_tracks:
        log(f"\nSummary: {len(failed_tracks)} tracks could not be downloaded from SoundCloud or YouTube:")
        
        # Categorize errors
        error_categories = {}
        for t in failed_tracks:
            category = categorize_error(t['reason'])
            if category not in error_categories:
                error_categories[category] = []
            error_categories[category].append(t)
        
        # Show categorized failures
        log("\n=== FAILURE ANALYSIS ===")
        for category, tracks in error_categories.items():
            log(f"{category}: {len(tracks)} tracks")
            for t in tracks:
                log_error(f"  - {t['title']} | {t['url']} | {t['reason']}")
        
        # Show overall failure breakdown
        log(f"\n=== FAILURE BREAKDOWN ===")
        for category, tracks in sorted(error_categories.items(), key=lambda x: len(x[1]), reverse=True):
            percentage = (len(tracks) / len(failed_tracks)) * 100
            log(f"{category}: {len(tracks)} tracks ({percentage:.1f}%)")
    else:
        log("All tracks downloaded successfully!")
    
    # Cleanup
    shutil.rmtree(download_folder)
    log(f"Cleaned up temp folder: {download_folder}")


def retry_soundcloud_download(track_info, download_folder):
    """Retry SoundCloud download with different settings and enhanced error logging"""
    url = track_info['url']
    title = track_info['title']
    
    log(f"Attempting SoundCloud retry for: {title}")
    log_debug(f"Retry URL: {url}")
    
    # Try multiple download strategies
    strategies = [
        # Strategy 1: Different audio quality and format options
        {
            'format': 'best[ext=mp3]/bestaudio[ext=mp3]/best/bestaudio',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',  # Lower quality to avoid issues
                },
                {'key': 'FFmpegMetadata'},
            ],
            'description': 'Lower quality MP3'
        },
        # Strategy 2: No post-processing, accept any format
        {
            'format': 'best/bestaudio',
            'postprocessors': [
                {'key': 'FFmpegMetadata'},
            ],
            'description': 'Any format, minimal processing'
        },
        # Strategy 3: Force different user agent and headers
        {
            'format': 'bestaudio/best',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
            ],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            'description': 'Different user agent'
        },
        # Strategy 4: Verbose mode to capture detailed errors
        {
            'format': 'bestaudio/best',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '160',
                },
            ],
            'description': 'Verbose mode for debugging',
            'verbose': True
        }
    ]
    
    strategy_errors = []
    
    for i, strategy in enumerate(strategies, 1):
        try:
            log(f"  Strategy {i}/{len(strategies)}: {strategy['description']}")
            
            # Create base options
            base_filename = sanitize_filename(title)
            output_template = os.path.join(download_folder, f"{base_filename}_retry.%(ext)s")
            
            ydl_opts = {
                'outtmpl': output_template,
                'format': strategy['format'],
                'postprocessors': strategy.get('postprocessors', []),
                'addmetadata': True,
                'quiet': not strategy.get('verbose', False),
                'no_warnings': not strategy.get('verbose', False),
                'ignoreerrors': False,  # Don't ignore errors for retry
                'retries': 3,
                'fragment_retries': 3,
                'verbose': strategy.get('verbose', False),
                'socket_timeout': 30,  # Timeout for retry attempts
            }
            
            # Add any additional options from strategy
            if 'http_headers' in strategy:
                ydl_opts['http_headers'] = strategy['http_headers']
            
            # Enhanced error capture for retry
            class RetryErrorHandler:
                def __init__(self, strategy_num):
                    self.errors = []
                    self.warnings = []
                    self.strategy_num = strategy_num
                
                def debug(self, msg):
                    if strategy.get('verbose', False):
                        log_debug(f"Strategy {self.strategy_num} yt-dlp: {msg}")
                
                def warning(self, msg):
                    self.warnings.append(msg)
                    log_warn(f"Strategy {self.strategy_num} warning: {msg}")
                
                def error(self, msg):
                    self.errors.append(msg)
                    log_error(f"Strategy {self.strategy_num} error: {msg}")
            
            error_handler = RetryErrorHandler(i)
            ydl_opts['logger'] = error_handler
            
            log_debug(f"  Starting yt-dlp with strategy {i}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Check if file was created
            expected_path = os.path.join(download_folder, f"{base_filename}_retry.mp3")
            if os.path.exists(expected_path):
                log(f"  ✓ Strategy {i} successful: {expected_path}")
                return expected_path
            
            # Check for any file with the base name (different extension)
            for file in os.listdir(download_folder):
                if file.startswith(f"{base_filename}_retry") and file.endswith(('.mp3', '.m4a', '.wav', '.flac', '.webm', '.ogg')):
                    file_path = os.path.join(download_folder, file)
                    log(f"  ✓ Strategy {i} successful (different format): {file_path}")
                    return file_path
            
            # If we get here, download "succeeded" but no file was created
            error_summary = f"No file created despite successful download"
            if error_handler.errors:
                error_summary += f"; Errors: {'; '.join(error_handler.errors)}"
            if error_handler.warnings:
                error_summary += f"; Warnings: {'; '.join(error_handler.warnings)}"
            
            strategy_errors.append(f"Strategy {i}: {error_summary}")
            log_error(f"  ✗ Strategy {i}: {error_summary}")
                    
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            strategy_errors.append(f"Strategy {i}: {error_msg}")
            log_error(f"  ✗ Strategy {i} failed: {error_msg}")
            continue
    
    # Log comprehensive failure summary
    log_error(f"  All {len(strategies)} retry strategies failed for: {title}")
    log_error(f"  Failure summary:")
    for error in strategy_errors:
        log_error(f"    - {error}")
    
    return None


def attempt_youtube_recovery(query, track_info, download_folder):
    """Attempt to recover a missing track using YouTube search with validation"""
    try:
        original_title = track_info.get('title', query)
        log_debug(f"YouTube recovery search: '{query}' for original: '{original_title}'")
        
        search_query = f"ytsearch8:{query}"  # Slightly more results to find better matches
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,
            'socket_timeout': 20,
            'retries': 2,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(search_query, download=False)
            if 'entries' in results:
                for entry in results['entries']:
                    if entry and entry.get('duration', 0) >= 30:
                        # Use the same validation as the other YouTube search
                        if is_relevant_youtube_match(original_title, entry):
                            log(f"Found relevant YouTube recovery candidate: {entry['title']} ({entry.get('duration', 0)}s)")
                            yt_file, yt_title, yt_dur, yt_artist, yt_cover = download_track(entry['webpage_url'], download_folder, verbose=VERBOSE_LOGGING)
                            if yt_file and os.path.exists(yt_file):
                                log_debug(f"Successfully recovered via YouTube: '{original_title}' -> '{yt_title}'")
                                return yt_file
                        else:
                            log_debug(f"Rejected irrelevant YouTube candidate: {entry['title']}")
        
        log_debug(f"No relevant YouTube matches found for: '{original_title}'")
        return None
    except Exception as e:
        log(f"YouTube recovery error for '{query}': {e}")
        return None

if __name__ == "__main__":
    main()
