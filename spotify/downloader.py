"""
Spotify downloader module.
Handles downloading single tracks and playlists from Spotify using YouTube as fallback.
Since Spotify doesn't allow direct downloads, this module searches YouTube for matching tracks.
"""

import os
import re
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
from shared.utils import (
    log, log_debug, log_error, log_warn, log_success, log_info,
    sanitize_filename, format_duration, get_session_id,
    is_relevant_youtube_match, analyze_failures, write_failed_tracks_file,
    VERBOSE_LOGGING, check_file_exists_in_folder, generate_unique_filename
)

class SpotifyDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        self.session_id = get_session_id()
        
    def extract_spotify_id(self, spotify_url):
        """Extract track or playlist ID from Spotify URL"""
        # Handle different Spotify URL formats
        patterns = [
            r'spotify:track:([a-zA-Z0-9]+)',
            r'spotify:playlist:([a-zA-Z0-9]+)',
            r'https://open\.spotify\.com/track/([a-zA-Z0-9]+)',
            r'https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)',
            r'https://open\.spotify\.com/album/([a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, spotify_url)
            if match:
                return match.group(1), pattern.split(':')[1] if 'spotify:' in pattern else pattern.split('/')[-2]
        
        return None, None

    def search_youtube_for_track(self, track_info, max_results=10):
        """Search YouTube for a Spotify track"""
        title = track_info.get('title', '')
        artist = track_info.get('artist', '')
        
        # Create multiple search queries for better matching
        search_queries = [
            f"{artist} {title}",
            f"{title} {artist}",
            f"{title} official",
            f"{artist} {title} official",
            f"{title} audio",
            title  # Fallback to just title
        ]
        
        log_debug(f"Searching YouTube for: '{title}' by '{artist}'")
        
        for query in search_queries:
            try:
                search_query = f"ytsearch{max_results}:{query}"
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
                                # Validate that this is actually a relevant match
                                if is_relevant_youtube_match(title, entry):
                                    log_debug(f"Found relevant YouTube match: {entry['title']}")
                                    return entry['webpage_url'], entry
                                else:
                                    log_debug(f"Rejected irrelevant match: {entry['title']}")
            except Exception as e:
                log_debug(f"YouTube search error for query '{query}': {e}")
                continue
        
        log_warn(f"No suitable YouTube matches found for: '{title}' by '{artist}'")
        return None, None

    def download_youtube_track(self, youtube_url, output_folder, track_info=None):
        """Download a track from YouTube"""
        try:
            log_debug(f"Downloading YouTube track: {youtube_url}")
            
            # Get track info first
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'socket_timeout': 15,
                'retries': 2,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                if not info:
                    log_error(f"Failed to extract YouTube track info: {youtube_url}")
                    return None, None, None, None, None
            
            # Use provided track info or extract from YouTube
            title = track_info.get('title', info.get('title', 'unknown_track')) if track_info else info.get('title', 'unknown_track')
            artist = track_info.get('artist', info.get('uploader', '')) if track_info else info.get('uploader', '')
            duration = info.get('duration', 0)
            
            # Clean title for filename and generate unique name
            clean_title = sanitize_filename(title)
            unique_filename = generate_unique_filename(output_folder, f"{clean_title}.mp3")
            output_template = os.path.join(output_folder, unique_filename.replace('.mp3', '.%(ext)s'))
            
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
                'quiet': not VERBOSE_LOGGING,
                'no_warnings': not VERBOSE_LOGGING,
                'ignoreerrors': True,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
            }
            
            # Add custom metadata if provided
            if track_info:
                ydl_opts['postprocessor_args'] = {
                    'ffmpeg': [
                        '-metadata', f"title={track_info.get('title', '')}",
                        '-metadata', f"artist={track_info.get('artist', '')}",
                        '-metadata', f"album={track_info.get('album', '')}",
                    ]
                }
            
            # Add error capture
            class DownloadErrorHandler:
                def __init__(self):
                    self.errors = []
                    self.warnings = []
                
                def debug(self, msg):
                    if VERBOSE_LOGGING:
                        log_debug(f"YouTube yt-dlp: {msg}")
                
                def warning(self, msg):
                    self.warnings.append(msg)
                    log_warn(f"YouTube yt-dlp warning: {msg}")
                
                def error(self, msg):
                    self.errors.append(msg)
                    log_error(f"YouTube yt-dlp error: {msg}")
            
            error_handler = DownloadErrorHandler()
            ydl_opts['logger'] = error_handler
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            
            # Check for download success
            base_filename = f"{clean_title}.mp3"
            output_path = os.path.join(output_folder, base_filename)
            
            if not os.path.exists(output_path):
                log_debug(f"Expected file not found: {output_path}")
                # Look for any file with similar name
                for file in os.listdir(output_folder):
                    if file.endswith('.mp3') and clean_title in file:
                        output_path = os.path.join(output_folder, file)
                        log_debug(f"Found similar file: {file}")
                        break
                else:
                    log_error(f"No output file found for '{title}' after download")
                    if error_handler.errors:
                        log_error(f"YouTube download errors: {'; '.join(error_handler.errors)}")
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
            
        except Exception as e:
            log_error(f"YouTube download exception for '{title}': {e}")
            return None, title, duration, artist, None

    def process_track(self, idx, track_info, total_tracks, download_folder, failed_tracks, downloaded_files):
        """Process a single Spotify track by searching YouTube"""
        try:
            title = track_info.get('title', 'Unknown Track')
            artist = track_info.get('artist', 'Unknown Artist')
            log(f"[{idx}/{total_tracks}] Processing Spotify track: '{title}' by '{artist}'")
            
            # Check if this track was already downloaded (prevent duplicates)
            existing_file = check_file_exists_in_folder(download_folder, f"{sanitize_filename(title)}.mp3")
            if existing_file and existing_file not in downloaded_files:
                log_debug(f"Track '{title}' already exists, skipping download")
                return existing_file
            
            # Search YouTube for the track
            youtube_url, youtube_info = self.search_youtube_for_track(track_info)
            
            if youtube_url:
                log_info(f"Found YouTube match: {youtube_info.get('title', 'Unknown')}")
                # Download from YouTube
                file_path, downloaded_title, duration, downloaded_artist, cover_art = self.download_youtube_track(
                    youtube_url, download_folder, track_info
                )
                
                if file_path and os.path.exists(file_path):
                    log_success(f"Downloaded '{downloaded_title}' by '{downloaded_artist}' ({format_duration(duration)})")
                    return file_path
                else:
                    log_error(f"Failed to download YouTube track for '{title}'")
                    failed_tracks.append({
                        'title': title,
                        'url': youtube_url,
                        'reason': 'YouTube download failed despite finding match'
                    })
                    return None
            else:
                log_error(f"No YouTube match found for '{title}' by '{artist}'")
                failed_tracks.append({
                    'title': title,
                    'url': f"Spotify track: {title} by {artist}",
                    'reason': 'No suitable YouTube match found'
                })
                return None
                
        except Exception as e:
            log_error(f"Error processing track {track_info.get('title', 'Unknown')}: {e}")
            failed_tracks.append({
                'title': track_info.get('title', 'Unknown'),
                'url': f"Spotify track: {track_info.get('title', 'Unknown')}",
                'reason': f'Exception: {e}'
            })
            return None

    def extract_playlist_tracks(self, playlist_url):
        """Extract track information from Spotify playlist URL using Spotify Web API"""
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            
            log(f"Attempting to extract tracks from Spotify playlist: {playlist_url}")
            
            # Check if user has set up Spotify API credentials
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                log_info("💡 SPOTIFY API SETUP (FREE):")
                log_info("1. Go to: https://developer.spotify.com/dashboard")
                log_info("2. Create a new app (free)")
                log_info("3. Copy Client ID and Client Secret")
                log_info("4. Set environment variables:")
                log_info("   Windows: set SPOTIFY_CLIENT_ID=your_client_id")
                log_info("   Windows: set SPOTIFY_CLIENT_SECRET=your_client_secret")
                log_info("   Linux/Mac: export SPOTIFY_CLIENT_ID=your_client_id")
                log_info("   Linux/Mac: export SPOTIFY_CLIENT_SECRET=your_client_secret")
                log_info("")
                log_info("Or create a .env file in the project root with:")
                log_info("SPOTIFY_CLIENT_ID=your_client_id")
                log_info("SPOTIFY_CLIENT_SECRET=your_client_secret")
                log_info("")
                log_info("This enables automatic playlist extraction!")
                return []
            
            # Initialize Spotify API
            client_credentials_manager = SpotifyClientCredentials(
                client_id=client_id, 
                client_secret=client_secret
            )
            sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            
            # Extract playlist ID
            playlist_id = self.extract_spotify_id(playlist_url)[0]
            
            # Get playlist tracks
            results = sp.playlist_tracks(playlist_id)
            tracks = []
            
            for item in results['items']:
                track = item['track']
                if track:
                    tracks.append({
                        'title': track['name'],
                        'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                        'url': f"Spotify track: {track['name']} by {track['artists'][0]['name'] if track['artists'] else 'Unknown Artist'}"
                    })
            
            # Handle pagination for large playlists
            while results['next']:
                results = sp.next(results)
                for item in results['items']:
                    track = item['track']
                    if track:
                        tracks.append({
                            'title': track['name'],
                            'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                            'url': f"Spotify track: {track['name']} by {track['artists'][0]['name'] if track['artists'] else 'Unknown Artist'}"
                        })
            
            if tracks:
                log_success(f"Successfully extracted {len(tracks)} tracks using Spotify API")
                return tracks
            else:
                log_warn("No tracks found in playlist")
                return []
                
        except ImportError:
            log_error("Spotify API library not installed")
            log_info("Install it with: pip install spotipy")
            log_info("Then set up your API credentials as shown above")
            return []
        except Exception as e:
            log_error(f"Spotify API error: {e}")
            log_info("Please check your API credentials and try again")
            return []
    

    def download_playlist(self, playlist_url, zip_filename=None, verbose=False):
        """Download a Spotify playlist by searching YouTube for each track"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        log(f"Processing Spotify playlist: {playlist_url}")
        
        # Extract playlist ID
        playlist_id, content_type = self.extract_spotify_id(playlist_url)
        if not playlist_id:
            log_error("Invalid Spotify URL format")
            return None
        
        log_info(f"Detected Spotify {content_type}: {playlist_id}")
        
        # Extract track information from the playlist
        tracks_info = self.extract_playlist_tracks(playlist_url)
        if not tracks_info:
            log_error("Failed to extract tracks from Spotify playlist")
            log_info("You can use --manual flag to enter track information manually")
            return None
        
        # Create playlist-specific folder
        playlist_name = f"Spotify_Playlist_{self.session_id}"
        download_folder = os.path.join(downloads_dir, playlist_name)
        os.makedirs(download_folder, exist_ok=True)
        
        log(f"Found {len(tracks_info)} tracks in playlist. Starting downloads...")
        
        final_files = []
        failed_tracks = []
        
        # Process each track
        downloaded_files = []  # Track all downloaded files to prevent duplicates
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_track = {
                executor.submit(self.process_track, idx, track_info, len(tracks_info), download_folder, failed_tracks, downloaded_files): track_info
                for idx, track_info in enumerate(tracks_info, 1)
            }
            
            for future in as_completed(future_to_track):
                result = future.result()
                if result and os.path.exists(result):
                    if result not in downloaded_files:  # Prevent duplicate entries
                        final_files.append(result)
                        downloaded_files.append(result)
                elif result:
                    log_warn(f"File not found after download: {result}")
        
        # Write failed tracks to a text file if any
        if failed_tracks:
            failed_txt_path = os.path.join(download_folder, "FAILED_DOWNLOADS.txt")
            write_failed_tracks_file(failed_tracks, failed_txt_path)
        
        # Analyze and report results
        analyze_failures(failed_tracks, len(tracks_info))
        
        if final_files:
            log_success(f"Successfully downloaded {len(final_files)} tracks to: {download_folder}")
            return download_folder
        else:
            log_error("No tracks were successfully downloaded")
            return None

    def download_single_track(self, track_url, zip_filename=None, verbose=False):
        """Download a single Spotify track by searching YouTube"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        log(f"Processing Spotify track: {track_url}")
        
        # Extract track ID
        track_id, content_type = self.extract_spotify_id(track_url)
        if not track_id or content_type != 'track':
            log_error("Invalid Spotify track URL format")
            return None
        
        log_info(f"Detected Spotify track: {track_id}")
        
        # For now, we'll return an error message about manual entry
        # In a full implementation, you would integrate with Spotify Web API
        log_error("Spotify track download requires Spotify Web API integration")
        log_info("For now, please use individual track URLs or implement Spotify API integration")
        log_info("You can use --manual flag to enter track information manually")
        
        return None

    def download_manual_tracks(self, tracks_info, zip_filename=None, verbose=False):
        """Download tracks manually entered by user"""
        if verbose:
            from shared.utils import set_verbose_logging
            set_verbose_logging(True)
        
        if not tracks_info:
            log_error("No track information provided")
            return None
        
        # Ensure downloads directory exists
        downloads_dir = os.path.join(os.getcwd(), self.output_dir)
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create playlist-specific folder for manual tracks
        playlist_name = f"Spotify_Manual_Tracks_{self.session_id}"
        download_folder = os.path.join(downloads_dir, playlist_name)
        os.makedirs(download_folder, exist_ok=True)
        
        final_files = []
        failed_tracks = []
        
        log(f"Processing {len(tracks_info)} manually entered tracks")
        
        # Process each track
        downloaded_files = []  # Track all downloaded files to prevent duplicates
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_track = {
                executor.submit(self.process_track, idx, track_info, len(tracks_info), download_folder, failed_tracks, downloaded_files): track_info
                for idx, track_info in enumerate(tracks_info, 1)
            }
            
            for future in as_completed(future_to_track):
                result = future.result()
                if result and os.path.exists(result):
                    if result not in downloaded_files:  # Prevent duplicate entries
                        final_files.append(result)
                        downloaded_files.append(result)
                elif result:
                    log_warn(f"File not found after download: {result}")
        
        # Write failed tracks to a text file if any
        if failed_tracks:
            failed_txt_path = os.path.join(download_folder, "FAILED_DOWNLOADS.txt")
            write_failed_tracks_file(failed_tracks, failed_txt_path)
        
        # Final summary
        log(f"\n=== FINAL SUMMARY ===")
        log(f"Total tracks processed: {len(tracks_info)}")
        log(f"Successfully downloaded: {len(final_files)}")
        log(f"Failed tracks: {len(failed_tracks)}")
        
        if failed_tracks:
            analyze_failures(failed_tracks)
        else:
            log_success("All tracks downloaded successfully!")
        
        log_success(f"Tracks downloaded to: {download_folder}")
        return download_folder
