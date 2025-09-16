#!/usr/bin/env python3
"""
Multi-Platform Music Downloader
A comprehensive tool for downloading music from SoundCloud, Spotify, and YouTube.

Usage:
    python main.py <platform> <type> <url> [options]

Platforms:
    soundcloud, spotify, youtube

Types:
    -song, -playlist

Options:
    --verbose, -v    Enable verbose logging
    --output, -o     Specify output filename (without .zip extension)
    --manual         For Spotify: manually enter track information
"""

import sys
import argparse
import os
from shared.utils import log, log_error, log_info, set_verbose_logging

# Import platform downloaders
from soundcloud.downloader import SoundCloudDownloader
from spotify.downloader import SpotifyDownloader
from youtube.downloader import YouTubeDownloader

def detect_platform_from_url(url):
    """Detect platform from URL"""
    url_lower = url.lower()
    if 'soundcloud.com' in url_lower or 'snd.sc' in url_lower:
        return 'soundcloud'
    elif 'spotify.com' in url_lower or 'spotify:' in url_lower:
        return 'spotify'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    return None

def detect_type_from_url(url):
    """Detect if URL is a track or playlist"""
    url_lower = url.lower()
    if any(keyword in url_lower for keyword in ['/playlist/', '/album/', 'playlist:', 'album:']):
        return 'playlist'
    elif any(keyword in url_lower for keyword in ['/track/', 'track:']):
        return 'song'
    return None

def get_manual_track_info():
    """Get track information manually from user input"""
    tracks = []
    log_info("Enter track information manually (press Enter with empty title to finish):")
    
    while True:
        print("\n" + "="*50)
        title = input("Track title (or press Enter to finish): ").strip()
        if not title:
            break
            
        artist = input("Artist name: ").strip()
        album = input("Album name (optional): ").strip()
        
        if title and artist:
            tracks.append({
                'title': title,
                'artist': artist,
                'album': album or 'Unknown Album'
            })
            log_info(f"Added: {title} by {artist}")
        else:
            log_error("Title and artist are required!")
    
    return tracks

def main():
    parser = argparse.ArgumentParser(
        description="Multi-Platform Music Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a SoundCloud playlist
  python main.py soundcloud playlist "https://soundcloud.com/user/sets/playlist-name"
  
  # Download a single YouTube track
  python main.py youtube song "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # Download with custom output name and verbose logging
  python main.py soundcloud playlist "URL" --output "my_playlist" --verbose
  
  # Manual Spotify track entry
  python main.py spotify song --manual
        """
    )
    
    parser.add_argument('platform', nargs='?', choices=['soundcloud', 'spotify', 'youtube'],
                       help='Music platform to download from')
    parser.add_argument('type', nargs='?', choices=['song', 'playlist'],
                       help='Type of content to download (song or playlist)')
    parser.add_argument('url', nargs='?',
                       help='URL of the track or playlist')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging for debugging')
    parser.add_argument('--output', '-o', type=str,
                       help='Output filename (without .zip extension)')
    parser.add_argument('--manual', action='store_true',
                       help='For Spotify: manually enter track information')
    
    args = parser.parse_args()
    
    # Handle legacy command line format
    if len(sys.argv) >= 2 and not args.platform:
        # Try to parse legacy format: python main.py <url> [--verbose]
        if sys.argv[1].startswith('http'):
            url = sys.argv[1]
            verbose = '--verbose' in sys.argv or '-v' in sys.argv
            output = None
            
            # Check for output filename in legacy format
            for i, arg in enumerate(sys.argv):
                if arg in ['--output', '-o'] and i + 1 < len(sys.argv):
                    output = sys.argv[i + 1]
                    break
            
            # Auto-detect platform and type
            platform = detect_platform_from_url(url)
            content_type = detect_type_from_url(url)
            
            if not platform:
                log_error("Could not detect platform from URL. Please specify platform explicitly.")
                log_info("Supported platforms: soundcloud, spotify, youtube")
                sys.exit(1)
            
            if not content_type:
                log_error("Could not detect content type from URL. Please specify -song or -playlist.")
                sys.exit(1)
            
            log_info(f"Auto-detected: {platform} {content_type}")
            
            # Set up arguments
            args.platform = platform
            args.type = content_type
            args.url = url
            args.verbose = verbose
            args.output = output
            args.manual = False
    
    # Validate arguments
    if not args.platform:
        log_error("Platform is required. Choose from: soundcloud, spotify, youtube")
        parser.print_help()
        sys.exit(1)
    
    if not args.type:
        log_error("Content type is required. Choose from: song, playlist")
        parser.print_help()
        sys.exit(1)
    
    if not args.manual and not args.url:
        log_error("URL is required unless using --manual flag")
        parser.print_help()
        sys.exit(1)
    
    # Set verbose logging
    if args.verbose:
        set_verbose_logging(True)
        log_info("Verbose logging enabled")
    
    # Initialize downloader based on platform
    try:
        if args.platform == 'soundcloud':
            downloader = SoundCloudDownloader()
        elif args.platform == 'spotify':
            downloader = SpotifyDownloader()
        elif args.platform == 'youtube':
            downloader = YouTubeDownloader()
        else:
            log_error(f"Unsupported platform: {args.platform}")
            sys.exit(1)
        
        log_info(f"Initialized {args.platform} downloader")
        
        # Handle different download scenarios
        if args.platform == 'spotify' and args.manual:
            # Manual track entry for Spotify
            if args.type != 'song':
                log_error("Manual mode is only supported for single tracks")
                sys.exit(1)
            
            tracks_info = get_manual_track_info()
            if not tracks_info:
                log_error("No tracks entered")
                sys.exit(1)
            
            log_info(f"Processing {len(tracks_info)} manually entered tracks")
            result = downloader.download_manual_tracks(
                tracks_info, 
                zip_filename=args.output,
                verbose=args.verbose
            )
        
        elif args.type == 'song':
            # Single track download
            log_info(f"Downloading single track from {args.platform}")
            result = downloader.download_single_track(
                args.url,
                zip_filename=args.output,
                verbose=args.verbose
            )
        
        elif args.type == 'playlist':
            # Playlist download
            log_info(f"Downloading playlist from {args.platform}")
            result = downloader.download_playlist(
                args.url,
                zip_filename=args.output,
                verbose=args.verbose
            )
        
        else:
            log_error(f"Invalid content type: {args.type}")
            sys.exit(1)
        
        # Handle result
        if result:
            log_info(f"Download completed successfully!")
            log_info(f"Output file: {result}")
        else:
            log_error("Download failed!")
            sys.exit(1)
    
    except KeyboardInterrupt:
        log_info("\nDownload cancelled by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
