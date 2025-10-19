"""
Worker Threads for Movie Sync
Separate threads for monitoring watchlist and downloading movies
"""

import threading
import time
import signal
import logging
from typing import Dict, Optional
from pathlib import Path
from queue_manager import QueueManager
from monitor import LetterboxdWatchlistMonitor
from filelist_downloader import FileListDownloader

# Module logger
logger = logging.getLogger(__name__)


def get_directory_size_gb(directory: Path) -> float:
    """
    Calculate total size of all files in directory (recursively)
    
    Args:
        directory: Path to directory
        
    Returns:
        Total size in gigabytes
    """
    if not directory.exists():
        return 0.0
    
    total_size = 0
    try:
        for item in directory.rglob('*'):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue
    except Exception as e:
        logger.warning(f"Error calculating directory size: {e}")
    
    # Convert bytes to gigabytes
    return total_size / (1024 ** 3)


class MonitorWorker(threading.Thread):
    """
    Worker thread that monitors Letterboxd watchlist
    Adds new movies to the pending queue
    """
    
    def __init__(self, username: str, queue_manager: QueueManager, 
                 check_interval: int = 3600, watchlist_file: Optional[str] = None):
        """
        Initialize monitor worker
        
        Args:
            username: Letterboxd username
            queue_manager: Shared queue manager instance
            check_interval: Seconds between watchlist checks
            watchlist_file: Path to watchlist cache file
        """
        super().__init__(daemon=True, name="MonitorWorker")
        
        self.username = username
        self.queue_manager = queue_manager
        self.check_interval = check_interval
        self.watchlist_file = watchlist_file
        self.monitor = LetterboxdWatchlistMonitor(username, watchlist_file)
        
        self.running = False
        self.stop_event = threading.Event()
    
    def run(self):
        """Main worker loop"""
        self.running = True
        logger.info(f"[MONITOR]  Monitor worker started (checking every {self.check_interval}s)")
        
        # Run immediately on start
        self._check_watchlist()
        
        # Then run periodically
        while not self.stop_event.is_set():
            # Wait for check_interval or until stopped
            if self.stop_event.wait(timeout=self.check_interval):
                break
            
            self._check_watchlist()
        
        self.running = False
        logger.info("[MONITOR]  Monitor worker stopped")
    
    def _check_watchlist(self):
        """Check watchlist and add new movies to queue"""
        try:
            # Separator
            logger.info("[CHECK]  Checking Letterboxd watchlist...")
            
            # Fetch current watchlist
            current_watchlist = self.monitor.get_watchlist()
            logger.info(f"[CHECK]  Found {len(current_watchlist)} movies in watchlist")
            
            # Load saved watchlist
            saved_watchlist = self.monitor.load_saved_watchlist()
            
            # Find new movies
            new_movies = self.monitor.find_new_movies(current_watchlist, saved_watchlist)

            added_count = 0
            if new_movies:
                logger.info(f"[NEW]  Found {len(new_movies)} new movie(s):")
            else:
                logger.info("No new movies found")
               
            for movie in current_watchlist:
                # Check if already completed
                if self.queue_manager.is_completed(movie.get('id')):
                    logger.debug(f"[OK]  {movie['title']} (already downloaded)")
                    continue
                
                # Add to pending queue
                if self.queue_manager.add_to_pending(movie):
                    director_info = f" - {movie.get('director', 'Unknown')}" if movie.get('director') != 'Unknown' else ''
                    logger.info(f"[NEW]  + {movie['title']}{director_info}")
                    added_count += 1
                else:
                    logger.debug(f"[SKIP]  {movie['title']} (already in queue)")
            
            if added_count > 0:
                logger.info(f"Added {added_count} movie(s) to download queue")
            
            # Track removed movies (movies no longer in watchlist)
            current_ids = [str(m.get('id', '')) for m in current_watchlist if m.get('id')]
            removed_count = self.queue_manager.mark_movies_as_removed(current_ids)
            if removed_count > 0:
                logger.info(f"[REMOVE]  Marked {removed_count} movie(s) for removal (no longer in watchlist)")
            
            # Save current watchlist
            self.monitor.save_watchlist(current_watchlist)
            
            # Show queue statistics
            stats = self.queue_manager.get_statistics()
            logger.info(f"[STATS]  Queue status: {stats['pending']} pending, "
                  f"{stats['failed']} failed, {stats['completed']} completed, "
                  f"{stats['removed']} removed")
            
        except Exception as e:
            logger.error(f"Error checking watchlist: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Stop the worker thread gracefully"""
        logger.info("[STOP]  Stopping monitor worker...")
        self.stop_event.set()
    
    def reload_config(self, config: Dict) -> None:
        """
        Reload configuration
        
        Args:
            config: New configuration dictionary
        """
        logger.info("[CONFIG] Reloading monitor worker config...")
        if 'check_interval' in config:
            self.check_interval = config['check_interval']
            logger.info(f"[CONFIG] Check interval updated to {self.check_interval}s")


class DownloadWorker(threading.Thread):
    """
    Worker thread that processes download queue
    Filters existing downloads, downloads movies, handles failures
    """
    
    def __init__(self, queue_manager: QueueManager, downloader: FileListDownloader,
                 download_dir: str, retry_interval: int = 3600, 
                 max_retries: int = 5, backoff_multiplier: float = 2.0,
                 max_download_space_gb: float = 0):
        """
        Initialize download worker
        
        Args:
            queue_manager: Shared queue manager instance
            downloader: FileList downloader instance
            download_dir: Directory where movies are downloaded
            retry_interval: Base retry interval in seconds (default: 1 hour)
            max_retries: Maximum number of retry attempts
            backoff_multiplier: Exponential backoff multiplier
            max_download_space_gb: Maximum total space for downloads in GB (0 = unlimited)
        """
        super().__init__(daemon=True, name="DownloadWorker")
        
        self.queue_manager = queue_manager
        self.downloader = downloader
        self.download_dir = Path(download_dir)
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.max_download_space_gb = max_download_space_gb
        
        self.running = False
        self.stop_event = threading.Event()
    
    def run(self):
        """Main worker loop"""
        self.running = True
        space_info = f" (space limit: {self.max_download_space_gb} GB)" if self.max_download_space_gb > 0 else " (unlimited space)"
        logger.info(f"[DOWNLOAD]  Download worker started (retry interval: {self.retry_interval}s{space_info})")
        
        # Log current space usage if limit is set
        if self.max_download_space_gb > 0:
            current_size_gb = get_directory_size_gb(self.download_dir)
            logger.info(f"[SPACE]  Current download directory size: {current_size_gb:.2f} GB / {self.max_download_space_gb} GB")
        
        # Process any pending downloads immediately
        self._process_pending_movies()
        
        # Then run periodically for retries
        while not self.stop_event.is_set():
            # Wait for retry_interval or until stopped
            if self.stop_event.wait(timeout=60):  # Check every minute
                break
            
            # Process pending queue
            self._process_pending_movies()
            
            # Process retries
            self._process_retries()
        
        self.running = False
        logger.info("[DOWNLOAD]  Download worker stopped")
    
    def _process_pending_movies(self):
        """Process movies from pending queue"""
        processed_ids = set()  # Track processed movies to avoid infinite loops with skipped items
        
        while not self.stop_event.is_set():
            # Get next movie from queue
            movie = self.queue_manager.get_next_pending()
            if not movie:
                break
            
            movie_id = str(movie.get('id', ''))
            
            # Skip movies marked as skipped (unless force_download is set)
            if movie.get('skipped', False) and not movie.get('force_download', False):
                logger.debug(f"[SKIP]  Skipping {movie.get('title', 'Unknown')} - marked as skipped")
                
                # Check if movie is already in pending queue
                already_in_queue = any(str(m.get('id')) == movie_id for m in self.queue_manager.pending_queue)
                
                # Put it back if not already there
                if not already_in_queue:
                    self.queue_manager.add_to_pending(movie)
                    logger.debug(f"[SKIP]  Added {movie.get('title', 'Unknown')} back to pending queue")
                
                # Track that we've seen this to avoid infinite processing in this cycle
                processed_ids.add(movie_id)
                continue
            
            try:
                self._download_movie(movie)
            except Exception as e:
                logger.error(f"Unexpected error processing {movie.get('title', 'Unknown')}: {e}")
                import traceback
                traceback.print_exc()
                
                # Add to failed queue
                retry_after = self._calculate_retry_time(movie.get('retry_count', 0))
                self.queue_manager.add_to_failed(
                    movie, 
                    f"Unexpected error: {str(e)}", 
                    retry_after
                )
            
            # Small delay between downloads to avoid rate limiting
            if not self.stop_event.is_set():
                time.sleep(2)
    
    def _process_retries(self):
        """Check for and process movies ready for retry"""
        ready_movies = self.queue_manager.get_movies_ready_for_retry(self.max_retries)
        
        if ready_movies:
            logger.info(f"[RETRY]  Processing {len(ready_movies)} movie(s) ready for retry...")
            for movie in ready_movies:
                if self.stop_event.is_set():
                    break
                
                # Skip movies marked as skipped
                if movie.get('skipped', False):
                    logger.debug(f"[SKIP]  Skipping retry for {movie.get('title', 'Unknown')} - marked as skipped")
                    continue
                
                logger.info(f"[RETRY]  Retrying: {movie['title']} (attempt {movie.get('retry_count', 0) + 1}/{self.max_retries})")
                self.queue_manager.move_failed_to_pending(movie)
    
    def _download_movie(self, movie: Dict):
        """
        Download a single movie with error handling
        
        Args:
            movie: Movie dictionary
        """
        title = movie.get('title', 'Unknown')
        force_download = movie.get('force_download', False)
        
        # Check if already downloaded (fuzzy matching)
        if self._is_movie_downloaded(movie):
            logger.info(f"{title} - Already downloaded")
            self.queue_manager.add_to_completed(movie)
            return
        
        # Check space limit before downloading (unless force_download is set)
        if not force_download and not self._check_space_available():
            logger.warning(f"[SPACE LIMIT]  Skipping {title} - download space limit reached "
                         f"({self.max_download_space_gb} GB)")
            # Move to failed queue with space limit marker
            movie['failed_reason'] = 'space_limit'
            error_msg = f"Download space limit reached ({self.max_download_space_gb} GB)"
            self.queue_manager.add_to_failed(movie, error_msg, retry_after=None)
            return
        
        if force_download:
            logger.info(f"[FORCE]  Force downloading {title} (ignoring space limit)")
            # Clear the force_download flag
            movie['force_download'] = False
        
        # Attempt download
        logger.info(f"[DOWNLOAD]  Processing: {title}")
        success = self.downloader.download_movie(movie)
        
        if success:
            logger.info(f"Successfully downloaded: {title}")
            self.queue_manager.add_to_completed(movie)
        else:
            # Download failed - determine reason and calculate retry
            retry_count = movie.get('retry_count', 0)
            retry_after = self._calculate_retry_time(retry_count)
            
            error_msg = "Download failed - will retry"
            if retry_count >= self.max_retries - 1:
                error_msg = "Download failed - max retries reached"
            
            logger.error(f"{error_msg}: {title}")
            self.queue_manager.add_to_failed(movie, error_msg, retry_after)
    
    def _check_space_available(self) -> bool:
        """
        Check if there's space available for more downloads
        
        Returns:
            True if space is available or limit is disabled (0), False if limit reached
        """
        # If limit is 0 or not set, unlimited space
        if not self.max_download_space_gb or self.max_download_space_gb <= 0:
            return True
        
        # Calculate current space usage
        current_size_gb = get_directory_size_gb(self.download_dir)
        
        # Check if we're under the limit
        if current_size_gb >= self.max_download_space_gb:
            logger.debug(f"[SPACE]  Current usage: {current_size_gb:.2f} GB / {self.max_download_space_gb} GB limit")
            return False
        
        return True
    
    def _is_movie_downloaded(self, movie: Dict) -> bool:
        """
        Check if movie is already downloaded using fuzzy matching
        
        Args:
            movie: Movie dictionary with title and year
            
        Returns:
            True if movie appears to be downloaded
        """
        if not self.download_dir.exists():
            return False
        
        from difflib import SequenceMatcher
        import re
        
        title = movie.get('title', '')
        year = movie.get('year', '')
        
        # Normalize title for matching
        normalized_title = title.lower().replace(' ', '.').replace(':', '').replace("'", '')
        
        # Search through files
        for file_path in self.download_dir.rglob('*'):
            if not file_path.is_file():
                continue
            
            filename = file_path.name.lower()
            
            # First check: if normalized title is in filename (fast and accurate)
            if normalized_title in filename:
                # If year is specified, verify it's also in the filename
                if year:
                    if str(year) in filename:
                        return True
                else:
                    # No year specified, title match is enough
                    return True
            
            # Second check: fuzzy matching on title portion only
            # Extract title portion (before quality indicators like 1080p, bluray, etc.)
            title_part = re.split(r'\d{3,4}p|bluray|brrip|webrip|hdtv|dvdrip|x264|x265|h264|h265', 
                                filename, flags=re.IGNORECASE)[0]
            
            # Calculate similarity
            similarity = SequenceMatcher(None, normalized_title, title_part).ratio()
            
            # Bonus for year match
            if year and str(year) in filename:
                similarity += 0.10
            
            # Lower threshold for fuzzy matching (75% instead of 85%)
            if similarity >= 0.75:
                return True
        
        return False
    
    def _calculate_retry_time(self, retry_count: int) -> int:
        """
        Calculate next retry time with exponential backoff
        
        Args:
            retry_count: Number of previous retry attempts
            
        Returns:
            Unix timestamp when to retry
        """
        # Exponential backoff: base_interval * (multiplier ^ retry_count)
        delay = self.retry_interval * (self.backoff_multiplier ** retry_count)
        
        # Cap at 24 hours
        delay = min(delay, 86400)
        
        return int(time.time() + delay)
    
    def stop(self):
        """Stop the worker thread gracefully"""
        logger.info("[STOP]  Stopping download worker...")
        self.stop_event.set()
    
    def reload_config(self, config: Dict) -> None:
        """
        Reload configuration
        
        Args:
            config: New configuration dictionary
        """
        logger.info("[CONFIG] Reloading download worker config...")
        if 'retry_interval' in config:
            self.retry_interval = config['retry_interval']
            logger.info(f"[CONFIG] Retry interval updated to {self.retry_interval}s")
        if 'max_retries' in config:
            self.max_retries = config['max_retries']
            logger.info(f"[CONFIG] Max retries updated to {self.max_retries}")
        if 'backoff_multiplier' in config:
            self.backoff_multiplier = config['backoff_multiplier']
            logger.info(f"[CONFIG] Backoff multiplier updated to {self.backoff_multiplier}")
        if 'max_download_space_gb' in config:
            self.max_download_space_gb = config['max_download_space_gb']
            logger.info(f"[CONFIG] Max download space updated to {self.max_download_space_gb} GB")


class CleanupWorker(threading.Thread):
    """
    Worker thread that handles cleanup of removed movies
    Deletes torrents, files, and qBittorrent entries after grace period
    """
    
    def __init__(self, queue_manager: QueueManager, cleanup_service,
                 check_interval: int = 3600, grace_period: int = 604800,
                 enabled: bool = False):
        """
        Initialize cleanup worker
        
        Args:
            queue_manager: Shared queue manager instance
            cleanup_service: CleanupService instance
            check_interval: Seconds between cleanup checks (default: 1 hour)
            grace_period: Seconds before deletion after removal (default: 7 days)
            enabled: Whether cleanup is enabled (default: False)
        """
        super().__init__(daemon=True, name="CleanupWorker")
        
        self.queue_manager = queue_manager
        self.cleanup_service = cleanup_service
        self.check_interval = check_interval
        self.grace_period = grace_period
        self.enabled = enabled
        
        self.running = False
        self.stop_event = threading.Event()
    
    def run(self):
        """Main worker loop"""
        self.running = True
        
        if not self.enabled:
            logger.warning(f"[CLEANUP]  Cleanup worker started (DISABLED - no deletions will occur)")
        else:
            logger.info(f"[CLEANUP]  Cleanup worker started (grace period: {self.grace_period}s, "
                  f"check interval: {self.check_interval}s)")
        
        # Run periodically
        while not self.stop_event.is_set():
            # Wait for check_interval or until stopped
            if self.stop_event.wait(timeout=self.check_interval):
                break
            
            if self.enabled:
                self._process_removals()
        
        self.running = False
        logger.info("[CLEANUP]  Cleanup worker stopped")
    
    def _process_removals(self):
        """Process movies ready for deletion"""
        try:
            # Get movies ready for deletion
            movies_to_delete = self.queue_manager.get_movies_ready_for_deletion(self.grace_period)
            
            if not movies_to_delete:
                return
            
            logger.info(f"[CLEANUP]  Processing {len(movies_to_delete)} movie(s) for cleanup...")
            
            for movie in movies_to_delete:
                # Skip movies marked as skipped
                if movie.get('skipped', False):
                    logger.debug(f"[SKIP]  Skipping cleanup for {movie.get('title', 'Unknown')} - marked as skipped")
                    continue
                
                title = movie.get('title', 'Unknown')
                year = movie.get('year', '')
                movie_id = str(movie.get('id', ''))
                removed_at = movie.get('removed_at', 0)
                
                if not movie_id:
                    continue
                
                logger.info(f"[DELETE]  Cleaning up: {title} ({year})")
                print(f"      Removed from watchlist: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(removed_at))}")
                
                # Perform cleanup
                results = self.cleanup_service.cleanup_movie(
                    movie,
                    delete_files=True,
                    delete_torrent=True,
                    remove_from_qbt=True
                )
                
                # Check if cleanup was successful
                if results['files_deleted'] or results['torrent_deleted'] or results['qbt_removed']:
                    # Remove from removed queue
                    self.queue_manager.remove_from_removed_queue(movie_id)
                    logger.info(f"Cleanup complete for: {title}")
                else:
                    logger.warning(f"No files found to delete for: {title}")
                    # Still remove from queue even if nothing was found
                    self.queue_manager.remove_from_removed_queue(movie_id)
                
                if results['errors']:
                    logger.warning(f"Errors during cleanup:")
                    for error in results['errors']:
                        print(f"         - {error}")
            
            logger.info(f"Cleanup processing complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Stop the worker thread gracefully"""
        logger.info("[STOP]  Stopping cleanup worker...")
        self.stop_event.set()
    
    def reload_config(self, config: Dict) -> None:
        """
        Reload configuration
        
        Args:
            config: New configuration dictionary
        """
        logger.info("[CONFIG] Reloading cleanup worker config...")
        if 'removal_grace_period' in config:
            self.grace_period = config['removal_grace_period']
            logger.info(f"[CONFIG] Grace period updated to {self.grace_period}s")
        if 'enable_removal_cleanup' in config:
            self.enabled = config['enable_removal_cleanup']
            status = "enabled" if self.enabled else "disabled"
            logger.info(f"[CONFIG] Cleanup {status}")



if __name__ == "__main__":
    print("Worker Threads Test")
    print("=" * 60)
    print("This module should be run via main.py, not directly.")
    print("Use: python main.py --threaded")
