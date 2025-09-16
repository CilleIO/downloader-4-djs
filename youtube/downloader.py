"""
YouTube downloader module.
Handles downloading single tracks and playlists from YouTube.
"""

import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
from shared.utils import (
    log, log_debug, log_error, log_warn, log_success, log_info,
    sanitize_filename, format_duration, get_session_id,
    analyze_failures, write_failed_tracks_file, VERBOSE_LOGGING
)

class YouTubeDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        self.session_id = get_session_id()
        
    def extract_playlist_tracks(self, playlist_url, max_retries=3):
        """Extract tracks from YouTube playlist with retry logic"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
        }
        
        for attempt in range(max_retries):
            try:
                log_debug(f"Extracting YouTube playlist (attempt {attempt + 1}/{max_retries})")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(playlist_url, download=False)
                    if not info:
                        log_warn(f"No playlist info returned on attempt {attempt + 1}")
                        continue
                        
                    if isinstance(info, dict):
                        if 'entries' in info:
                            tracks = []
                            for entry in info['entries']:
                                if isinstance(entry, dict) and 'url' in entry:
                                    # Filter out non-video entries and very long videos (likely live streams)
                                    duration = entry.get('duration', 0)
                                    if duration and duration < 3600:  # Less than 1 hour
                                        tracks.append(entry['url'])
                                    elif not duration:  # If duration is unknown, include it
                                        tracks.append(entry['url'])
                            log_debug(f"Successfully extracted {len(tracks)} tracks")
                            return tracks
                        if 'url' in info:
                            return [info['url']]
            except Exception as e:
                log_warn(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    wait_time = (attempt + 1) * 5
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
            'socket_timeout': 15,
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
                    time.sleep(2)
                else:
                    log_debug(f"Failed to get track info after {max_retries} attempts: {url}")
        
        return None

    def download_track(self, url, output_folder, verbose=False):
        """Download a YouTube track with enhanced error logging"""
        log_debug(f"Starting YouTube download for: {url}")
        
        info = self.get_track_info(url)
        if not info:
            log_error(f"Failed to extract track info for: {url}")
            return None, None, None, None, None
            
        title = info.get('title', 'unknown_track')
        duration = info.get('duration', 0)
        artist = info.get('uploader') or info.get('channel') or ''
        
        log_debug(f"Track info - Title: '{title}', Artist: '{artist}', Duration: {duration}s")
        
        # Clean title for filename
        clean_title = sanitize_filename(title)
        output_template = os.path.join(output_folder, f"{clean_title}.%(ext)s")
        
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
        base_filename = f"{clean_title}.mp3"
        output_path = os.path.join(output_folder, base_filename)
        
        if not os.path.exists(output_path):
            log_debug(f"Expected file not found: {output_path}")
            log_debug(f"Searching for similar files in: {output_folder}")
            
            # Look for any file with similar name
            found_file = None
            for file in os.listdir(output_folder):
                if file.endswith('.mp3') and clean_title in file:
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
            thumb_path = os.path.join(output_folder, f"{clean_title}.{ext}")
            if os.path.exists(thumb_path):
                cover_art = thumb_path
                log_debug(f"Found cover art: {thumb_path}")
                break
        
        log_debug(f"Successfully downloaded: {output_path}")
        return output_path, title, duration, artist, cover_art

    def process_track(self, idx, track_url, total_tracks, download_folder, failed_tracks):
        """Process a single YouTube track"""
        try:
            log(f"[{idx}/{total_tracks}] Downloading YouTube track: {track_url}")
            file_path, title, duration, artist, cover_art = self.download_track(track_url, download_folder, verbose=VERBOSE_LOGGING)
            
            if file_path and duration is not None:
                if os.path.exists(file_path):
                    log_success(f"Downloaded '{title}' by '{artist}' ({format_duration(duration)})")
                    return file_path
                else:
                    failed_tracks.append({'title': title, 'url': track_url, 'reason': 'yt_dlp reported success but file missing'})
                    log_warn(f"yt_dlp reported success but file missing: {file_path}")
                    return None
            else:
                log_error(f"Failed to download track from YouTube: {track_url}")
                failed_tracks.append({'title': title, 'url': track_url, 'reason': 'YouTube download failed'})
                return None
                
        except Exception as e:
            log_error(f"Error processing track {track_url}: {e}")
            failed_tracks.append({'title': track_url, 'url': track_url, 'reason': f'Exception: {e}'})
            return None

    def download_playlist(self, playlist_url, zip_filename=None, verbose=False):
        """Download a complete YouTube playlist"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create playlist-specific folder
        playlist_name = f"YouTube_Playlist_{self.session_id}"
        download_folder = os.path.join(downloads_dir, playlist_name)
        os.makedirs(download_folder, exist_ok=True)
        
        log(f"Extracting YouTube tracks from playlist: {playlist_url}")
        track_urls = self.extract_playlist_tracks(playlist_url)
        original_track_count = len(track_urls)
        log(f"Found {original_track_count} tracks in playlist.")
        
        # Exit early if no tracks found
        if original_track_count == 0:
            log_error("No tracks found. The playlist might be private or the URL might be invalid.")
            return None
        
        # download_folder already set above
        
        final_files = []
        failed_tracks = []
        successful_track_urls = []
        track_url_info_map = {}
        
        # Pre-fetch track info for metadata enhancement later
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
        
        # Process in batches of 50
        batch_size = 50
        total_batches = (len(track_urls) + batch_size - 1) // batch_size
        
        with ThreadPoolExecutor(max_workers=3) as info_executor:
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
            max_workers = min(6, max(1, len(track_urls)))
            log(f"Large playlist detected ({original_track_count} tracks), reducing concurrency to {max_workers} workers")
        else:
            max_workers = min(8, max(1, len(track_urls)))
        
        # Download tracks
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.process_track, idx, url, len(track_urls), download_folder, failed_tracks): url
                for idx, url in enumerate(track_urls, 1)
            }
            
            for future in as_completed(future_to_url):
                result = future.result()
                if result and os.path.exists(result):
                    final_files.append(result)
                    successful_track_urls.append(future_to_url[future])
                elif result:
                    log_warn(f"File not found after download: {result}")
        
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
        """Download a single YouTube track"""
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
        
        log(f"Downloading single YouTube track: {track_url}")
        
        # Download the track
        file_path, title, duration, artist, cover_art = self.download_track(track_url, download_folder, verbose=VERBOSE_LOGGING)
        
        if file_path and duration is not None and os.path.exists(file_path):
            log_success(f"Downloaded '{title}' by '{artist}' ({format_duration(duration)})")
            final_files.append(file_path)
        else:
            log_error(f"Failed to download track from YouTube: {track_url}")
            failed_tracks.append({'title': title, 'url': track_url, 'reason': 'YouTube download failed'})
        
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
