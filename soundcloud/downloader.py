"""
SoundCloud downloader module.
Handles downloading single tracks and playlists from SoundCloud.
"""

import os
import time
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
from shared.utils import (
    log, log_debug, log_error, log_warn, log_success,
    sanitize_filename, format_duration, get_session_id,
    is_relevant_youtube_match, analyze_failures, write_failed_tracks_file,
    embed_metadata_and_cover, download_cover_art, VERBOSE_LOGGING,
    check_file_exists_in_folder, generate_unique_filename
)

class SoundCloudDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        self.session_id = get_session_id()
        
    def extract_tracks(self, playlist_url, max_retries=3):
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
                log_debug(f"Extracting SoundCloud playlist (attempt {attempt + 1}/{max_retries})")
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
                    wait_time = (attempt + 1) * 5  # Progressive backoff: 5s, 10s, 15s
                    log(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    log_error(f"All {max_retries} attempts failed to extract playlist")
        
        return []

    def get_track_info(self, url, max_retries=2):
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
                    time.sleep(2)  # Short wait
                else:
                    log_debug(f"Failed to get track info after {max_retries} attempts: {url}")
        
        return None

    def download_track(self, url, output_folder, verbose=False):
        """Download a track with enhanced error logging"""
        log_debug(f"Starting SoundCloud download for: {url}")
        
        info = self.get_track_info(url)
        if not info:
            log_error(f"Failed to extract track info for: {url}")
            return None, None, None, None, None
            
        title = info.get('title', 'unknown_track')
        duration = info.get('duration', 0)
        artist = info.get('artist') or info.get('uploader') or info.get('creator') or ''
        
        log_debug(f"Track info - Title: '{title}', Artist: '{artist}', Duration: {duration}s")
        
        # Output template: just the title (no numbering, no artist)
        # Use consistent filename for duplicate prevention
        clean_title = sanitize_filename(title)
        base_filename = f"{clean_title}.mp3"
        
        # Check if file already exists and use existing filename if it does
        existing_file = check_file_exists_in_folder(output_folder, base_filename)
        if existing_file:
            log_debug(f"Using existing file: {existing_file}")
            # Return the existing file with original metadata
            return existing_file, title, duration, artist, None
        
        # Generate unique filename only if needed
        unique_filename = generate_unique_filename(output_folder, base_filename)
        output_template = os.path.join(output_folder, unique_filename.replace('.mp3', '.%(ext)s'))
        
        # Check for SoundCloud authentication credentials
        soundcloud_username = os.getenv('SOUNDCLOUD_USERNAME')
        soundcloud_password = os.getenv('SOUNDCLOUD_PASSWORD')
        soundcloud_cookies = os.getenv('SOUNDCLOUD_COOKIES')
        
        # Check if this is a YouTube URL (for fallback downloads)
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        
        if is_youtube:
            # Use improved YouTube settings
            ydl_opts = {
                'outtmpl': output_template,
                'format': 'bestaudio[ext=m4a]/bestaudio/best[ext=m4a]/bestaudio/best',
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
                'quiet': not verbose,
                'no_warnings': not verbose,
                'ignoreerrors': True,
                'socket_timeout': 30,
                'retries': 5,
                'fragment_retries': 5,
                'extractor_retries': 3,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
            }
        else:
            # Use SoundCloud settings
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
                'quiet': not verbose,
                'no_warnings': not verbose,
                'ignoreerrors': True,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
            }
            
            # Add SoundCloud authentication if credentials are provided
            if soundcloud_username and soundcloud_password:
                ydl_opts['username'] = soundcloud_username
                ydl_opts['password'] = soundcloud_password
                log_debug("Using SoundCloud username/password authentication")
            elif soundcloud_cookies:
                ydl_opts['cookies'] = soundcloud_cookies
                log_debug("Using SoundCloud cookies authentication")
            else:
                log_debug("No SoundCloud authentication provided - using anonymous access")
        
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
        sanitized_title = sanitize_filename(title)
        base_filename = f"{sanitized_title}.mp3"
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
        
        # Embed metadata to preserve original title
        track_info = {
            'title': title,
            'artist': artist,
            'album': f'SoundCloud Playlist {self.session_id}'
        }
        embed_metadata_and_cover(output_path, track_info, cover_art)
        
        log_debug(f"Successfully downloaded: {output_path}")
        return output_path, title, duration, artist, cover_art

    def search_youtube_for_longer_version(self, title, min_duration=31):
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

    def retry_soundcloud_download(self, track_info, download_folder):
        """Retry SoundCloud download with different settings and enhanced error logging"""
        url = track_info['url']
        title = track_info['title']
        
        # Check if file already exists to prevent duplicates
        existing_file = check_file_exists_in_folder(download_folder, f"{sanitize_filename(title)}.mp3")
        if existing_file and os.path.exists(existing_file):
            log_debug(f"Track '{title}' already exists, skipping retry")
            return existing_file
        
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

    def attempt_youtube_recovery(self, query, track_info, download_folder):
        """Attempt to recover a missing track using YouTube search with validation"""
        try:
            original_title = track_info.get('title', query)
            
            # Check if file already exists to prevent duplicates
            existing_file = check_file_exists_in_folder(download_folder, f"{sanitize_filename(original_title)}.mp3")
            if existing_file and os.path.exists(existing_file):
                log_debug(f"Track '{original_title}' already exists, skipping YouTube recovery")
                return existing_file
            
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
                                yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(entry['webpage_url'], download_folder, verbose=VERBOSE_LOGGING)
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

    def process_track(self, idx, track_url, total_tracks, download_folder, failed_tracks, downloaded_files):
        """Process a single track with fallback logic"""
        try:
            log(f"[{idx}/{total_tracks}] Downloading SoundCloud track: {track_url}")
            
            # Check if this track was already downloaded (prevent duplicates)
            track_info = self.get_track_info(track_url)
            if track_info:
                title = track_info.get('title', 'unknown_track')
                # Check if a file with this title already exists
                existing_file = check_file_exists_in_folder(download_folder, f"{sanitize_filename(title)}.mp3")
                if existing_file and existing_file not in downloaded_files:
                    log_debug(f"Track '{title}' already exists, skipping download")
                    return existing_file
            else:
                title = 'unknown_track'
            
            sc_file, title, duration, artist, cover_art = self.download_track(track_url, download_folder, verbose=VERBOSE_LOGGING)
            if sc_file and duration is not None:
                if os.path.exists(sc_file):
                    log_success(f"Downloaded '{title}' by '{artist}' ({format_duration(duration)})")
                    if duration <= 30:
                        log(f"Track '{title}' is {duration}s (<=30s). Searching YouTube for longer version...")
                        yt_url, yt_duration = self.search_youtube_for_longer_version(title)
                        if yt_url:
                            log(f"Found YouTube version: {yt_url} ({yt_duration}s). Downloading...")
                            yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                            if yt_file and yt_dur > duration and os.path.exists(yt_file):
                                log_success(f"Replaced with YouTube version: '{yt_title}' by '{yt_artist}' ({format_duration(yt_dur)})")
                                try:
                                    os.remove(sc_file)
                                except Exception as e:
                                    log(f"Failed to remove short SC file: {e}")
                                return yt_file
                            elif yt_file and not os.path.exists(yt_file):
                                failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                                log_warn(f"YouTube download reported success but file missing: {yt_file}")
                            else:
                                log(f"YouTube version not found or not longer. Keeping original.")
                        else:
                            log(f"No suitable YouTube version found. Keeping original.")
                    return sc_file
                else:
                    failed_tracks.append({'title': title, 'url': track_url, 'reason': 'yt_dlp reported success but file missing (possible duplicate title or yt_dlp error)'})
                    log_warn(f"yt_dlp reported success but file missing: {sc_file}")
                    # Try YouTube fallback for missing file
                    yt_url, yt_duration = self.search_youtube_for_longer_version(title)
                    if yt_url:
                        log(f"Trying YouTube fallback for '{title}': {yt_url}")
                        yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                        if yt_file and os.path.exists(yt_file):
                            log_success(f"Successfully downloaded from YouTube: '{yt_title}' by '{yt_artist}'")
                            return yt_file
                        elif yt_file and not os.path.exists(yt_file):
                            failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                            log_warn(f"YouTube download reported success but file missing: {yt_file}")
                        else:
                            log(f"Failed to download from YouTube: {yt_url}")
                            failed_tracks.append({'title': title, 'url': yt_url, 'reason': 'Failed on SoundCloud (file missing) and YouTube download'})
                    else:
                        failed_tracks.append({'title': title, 'url': track_url, 'reason': 'Failed on SoundCloud (file missing), no suitable YouTube match'})
                    return None
            else:
                log_error(f"Failed to download track from SoundCloud: {track_url}")
                # Try YouTube fallback
                info = self.get_track_info(track_url)
                title = info.get('title', 'unknown_track') if info else track_url
                yt_url, yt_duration = self.search_youtube_for_longer_version(title)
                if yt_url:
                    log(f"Trying YouTube fallback for '{title}': {yt_url}")
                    yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                    if yt_file and os.path.exists(yt_file):
                        log_success(f"Successfully downloaded from YouTube: '{yt_title}' by '{yt_artist}'")
                        return yt_file
                    elif yt_file and not os.path.exists(yt_file):
                        failed_tracks.append({'title': yt_title, 'url': yt_url, 'reason': 'YouTube download reported success but file missing'})
                        log_warn(f"YouTube download reported success but file missing: {yt_file}")
                    else:
                        log(f"Failed to download from YouTube: {yt_url}")
                        failed_tracks.append({'title': title, 'url': yt_url, 'reason': 'Failed on SoundCloud and YouTube download'})
                else:
                    failed_tracks.append({'title': title, 'url': track_url, 'reason': 'Failed on SoundCloud, no suitable YouTube match'})
                return None
        except Exception as e:
            log_error(f"Error processing track {track_url}: {e}")
            failed_tracks.append({'title': track_url, 'url': track_url, 'reason': f'Exception: {e}'})
            return None

    def download_playlist(self, playlist_url, zip_filename=None, verbose=False):
        """Download a complete SoundCloud playlist"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create playlist-specific folder
        playlist_name = f"SoundCloud_Playlist_{self.session_id}"
        download_folder = os.path.join(downloads_dir, playlist_name)
        os.makedirs(download_folder, exist_ok=True)
        
        log(f"Extracting SoundCloud tracks from playlist: {playlist_url}")
        track_urls = self.extract_tracks(playlist_url)
        original_track_count = len(track_urls)
        log(f"Found {original_track_count} tracks in playlist.")
        
        # Exit early if no tracks found
        if original_track_count == 0:
            log_error("No tracks found. The playlist might be private or the URL might be invalid.")
            return None
        
        # download_folder already set above
        
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
                    info = self.get_track_info(url)
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
        
        # Initial download attempt
        downloaded_files = []  # Track all downloaded files to prevent duplicates
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.process_track, idx, url, len(track_urls), download_folder, failed_tracks, downloaded_files): url
                for idx, url in enumerate(track_urls, 1)
            }
            
            for future in as_completed(future_to_url):
                result = future.result()
                if result and os.path.exists(result):
                    if result not in downloaded_files:  # Prevent duplicate entries
                        final_files.append(result)
                        downloaded_files.append(result)
                    successful_track_urls.append(future_to_url[future])  # Track successful URL
                elif result:
                    log_warn(f"File not found after download: {result}")
        
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
                    info = self.get_track_info(url)
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
                        future = executor.submit(self.retry_soundcloud_download, track, download_folder)
                        sc_retry_futures.append((future, track))
                    
                    for future, track in sc_retry_futures:
                        try:
                            result = future.result()
                            if result and os.path.exists(result):
                                # Check if this file is already in our downloaded files
                                if result not in downloaded_files:
                                    recovery_files.append(result)
                                    downloaded_files.append(result)
                                    log_success(f"SoundCloud retry successful: '{track['title']}'")
                                else:
                                    log_debug(f"SoundCloud retry file already exists: '{track['title']}'")
                            else:
                                soundcloud_retry_failed.append(track)
                                log_error(f"SoundCloud retry failed: '{track['title']}'")
                        except Exception as e:
                            log_error(f"SoundCloud retry error for '{track['title']}': {e}")
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
                                future = executor.submit(self.attempt_youtube_recovery, query, track, download_folder)
                                yt_recovery_futures.append((future, track))
                                break  # Try first query, if it fails we'll try others
                        
                        for future, track in yt_recovery_futures:
                            try:
                                result = future.result()
                                if result and os.path.exists(result):
                                    recovery_files.append(result)
                                    log_success(f"YouTube recovery successful: '{track['title']}'")
                                else:
                                    # Try additional search queries if first failed
                                    yt_recovered = False
                                    for query in [f"{track['title']} official", f"{track['title']} audio", track['title']]:
                                        result = self.attempt_youtube_recovery(query, track, download_folder)
                                        if result and os.path.exists(result):
                                            recovery_files.append(result)
                                            log_success(f"YouTube recovery successful with alternate search: '{track['title']}'")
                                            yt_recovered = True
                                            break
                                    
                                    if not yt_recovered:
                                        log_error(f"Complete failure: '{track['title']}'")
                                        failed_tracks.append({
                                            'title': track['title'], 
                                            'url': track['url'], 
                                            'reason': 'Failed SoundCloud retry and YouTube fallback after cross-referencing'
                                        })
                            except Exception as e:
                                log_error(f"YouTube recovery error for '{track['title']}': {e}")
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
        
        # Write failed tracks to a text file if any
        if failed_tracks:
            failed_txt_path = os.path.join(download_folder, "FAILED_DOWNLOADS.txt")
            write_failed_tracks_file(failed_tracks, failed_txt_path)
        
        # Final summary
        log(f"\n=== FINAL SUMMARY ===")
        log(f"Original tracks: {original_track_count}")
        log(f"Successfully downloaded: {len(final_files)}")
        log(f"Failed tracks: {len(failed_tracks)}")
        
        if failed_tracks:
            analyze_failures(failed_tracks)
        else:
            log_success("All tracks downloaded successfully!")
        
        log_success(f"Playlist downloaded to: {download_folder}")
        return download_folder

    def download_single_track(self, track_url, zip_filename=None, verbose=False):
        """Download a single SoundCloud track"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        # For single tracks, download directly to the downloads folder
        download_folder = downloads_dir
        
        failed_tracks = []
        final_files = []
        
        log(f"Downloading single SoundCloud track: {track_url}")
        
        # Download the track
        sc_file, title, duration, artist, cover_art = self.download_track(track_url, download_folder, verbose=VERBOSE_LOGGING)
        
        if sc_file and duration is not None and os.path.exists(sc_file):
            log_success(f"Downloaded '{title}' by '{artist}' ({format_duration(duration)})")
            final_files.append(sc_file)
            
            # Check if track is too short and search for longer version
            if duration <= 30:
                log(f"Track '{title}' is {duration}s (<=30s). Searching YouTube for longer version...")
                yt_url, yt_duration = self.search_youtube_for_longer_version(title)
                if yt_url:
                    log(f"Found YouTube version: {yt_url} ({yt_duration}s). Downloading...")
                    yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                    if yt_file and yt_dur > duration and os.path.exists(yt_file):
                        log_success(f"Replaced with YouTube version: '{yt_title}' by '{yt_artist}' ({format_duration(yt_dur)})")
                        try:
                            os.remove(sc_file)
                            # Update final_files to use the YouTube version
                            final_files = [yt_file]
                        except Exception as e:
                            log(f"Failed to remove short SC file: {e}")
                            final_files.append(yt_file)
                    else:
                        log(f"YouTube version not found or not longer. Keeping original.")
        else:
            log_error(f"Failed to download track from SoundCloud: {track_url}")
            # Try YouTube fallback
            info = self.get_track_info(track_url)
            title = info.get('title', 'unknown_track') if info else track_url
            yt_url, yt_duration = self.search_youtube_for_longer_version(title)
            if yt_url:
                log(f"Trying YouTube fallback for '{title}': {yt_url}")
                yt_file, yt_title, yt_dur, yt_artist, yt_cover = self.download_track(yt_url, download_folder, verbose=VERBOSE_LOGGING)
                if yt_file and os.path.exists(yt_file):
                    log_success(f"Successfully downloaded from YouTube: '{yt_title}' by '{yt_artist}'")
                    final_files.append(yt_file)
                else:
                    failed_tracks.append({'title': title, 'url': yt_url, 'reason': 'Failed on SoundCloud and YouTube download'})
            else:
                failed_tracks.append({'title': title, 'url': track_url, 'reason': 'Failed on SoundCloud, no suitable YouTube match'})
        
        # Write failed tracks to a text file if any
        if failed_tracks:
            failed_txt_path = os.path.join(download_folder, f"FAILED_DOWNLOADS_{self.session_id}.txt")
            write_failed_tracks_file(failed_tracks, failed_txt_path)
        
        # Final summary
        log(f"\n=== FINAL SUMMARY ===")
        if final_files and not failed_tracks:
            log_success("Track downloaded successfully!")
            log_success(f"Track saved to: {download_folder}")
        elif final_files:
            log(f"Track downloaded with {len(failed_tracks)} failures")
            log_success(f"Track saved to: {download_folder}")
        else:
            log_error("Track download failed!")
        
        if failed_tracks:
            analyze_failures(failed_tracks)
        
        return download_folder if final_files else None
