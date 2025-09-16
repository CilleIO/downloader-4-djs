# Downloads Folder

This folder contains all downloaded music tracks and playlists organized by platform and session.

## Folder Structure

- **Single tracks**: Downloaded directly to this folder
- **Playlists**: Downloaded to subfolders with session-specific names
  - `SoundCloud_Playlist_[session_id]/`
  - `Spotify_Manual_Tracks_[session_id]/`
  - `YouTube_Playlist_[session_id]/`

## File Organization

- All audio files are converted to MP3 format
- Metadata and cover art are embedded automatically
- Failed downloads are logged to `FAILED_DOWNLOADS.txt` files

## Notes

- This folder is ignored by Git (except for this README)
- Downloaded content is not committed to the repository
- The folder structure is preserved for organization purposes
