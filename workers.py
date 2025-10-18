"""
Worker Threads for Movie Sync
Separate threads for monitoring watchlist and downloading movies
"""

import threading
import time
import signal
from typing import Dict, Optional
from pathlib import Path
from queue_manager import QueueManager
from monitor import LetterboxdWatchlistMonitor
from filelist_downloader import FileListDownloader


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
        print(f"🎬 Monitor worker started (checking every {self.check_interval}s)")
        
        # Run immediately on start
        self._check_watchlist()
        
        # Then run periodically
        while not self.stop_event.is_set():
            # Wait for check_interval or until stopped
            if self.stop_event.wait(timeout=self.check_interval):
                break
            
            self._check_watchlist()
        
        self.running = False
        print("🎬 Monitor worker stopped")
    
    def _check_watchlist(self):
        """Check watchlist and add new movies to queue"""
        try:
            print("\n" + "=" * 70)
            print("📺 Checking Letterboxd watchlist...")
            
            # Fetch current watchlist
            current_watchlist = self.monitor.get_watchlist()
            print(f"   Found {len(current_watchlist)} movies in watchlist")
            
            # Load saved watchlist
            saved_watchlist = self.monitor.load_saved_watchlist()
            
            # Find new movies
            new_movies = self.monitor.find_new_movies(current_watchlist, saved_watchlist)
            
            if new_movies:
                print(f"   🆕 Found {len(new_movies)} new movie(s):")
                added_count = 0
                
                for movie in new_movies:
                    # Check if already completed
                    if self.queue_manager.is_completed(movie.get('id')):
                        print(f"      ✓ {movie['title']} (already downloaded)")
                        continue
                    
                    # Add to pending queue
                    if self.queue_manager.add_to_pending(movie):
                        director_info = f" - {movie.get('director', 'Unknown')}" if movie.get('director') != 'Unknown' else ''
                        print(f"      + {movie['title']}{director_info}")
                        added_count += 1
                    else:
                        print(f"      ⏭ {movie['title']} (already in queue)")
                
                if added_count > 0:
                    print(f"   ✓ Added {added_count} movie(s) to download queue")
            else:
                print("   ✓ No new movies found")
            
            # Save current watchlist
            self.monitor.save_watchlist(current_watchlist)
            
            # Show queue statistics
            stats = self.queue_manager.get_statistics()
            print(f"   📊 Queue status: {stats['pending']} pending, "
                  f"{stats['failed']} failed, {stats['completed']} completed")
            
        except Exception as e:
            print(f"   ✗ Error checking watchlist: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Stop the worker thread gracefully"""
        print("🛑 Stopping monitor worker...")
        self.stop_event.set()


class DownloadWorker(threading.Thread):
    """
    Worker thread that processes download queue
    Filters existing downloads, downloads movies, handles failures
    """
    
    def __init__(self, queue_manager: QueueManager, downloader: FileListDownloader,
                 download_dir: str, retry_interval: int = 3600, 
                 max_retries: int = 5, backoff_multiplier: float = 2.0):
        """
        Initialize download worker
        
        Args:
            queue_manager: Shared queue manager instance
            downloader: FileList downloader instance
            download_dir: Directory where movies are downloaded
            retry_interval: Base retry interval in seconds (default: 1 hour)
            max_retries: Maximum number of retry attempts
            backoff_multiplier: Exponential backoff multiplier
        """
        super().__init__(daemon=True, name="DownloadWorker")
        
        self.queue_manager = queue_manager
        self.downloader = downloader
        self.download_dir = Path(download_dir)
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        
        self.running = False
        self.stop_event = threading.Event()
    
    def run(self):
        """Main worker loop"""
        self.running = True
        print(f"⬇️  Download worker started (retry interval: {self.retry_interval}s)")
        
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
        print("⬇️  Download worker stopped")
    
    def _process_pending_movies(self):
        """Process movies from pending queue"""
        while not self.stop_event.is_set():
            # Get next movie from queue
            movie = self.queue_manager.get_next_pending()
            if not movie:
                break
            
            try:
                self._download_movie(movie)
            except Exception as e:
                print(f"✗ Unexpected error processing {movie.get('title', 'Unknown')}: {e}")
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
            print(f"\n🔄 Processing {len(ready_movies)} movie(s) ready for retry...")
            for movie in ready_movies:
                if self.stop_event.is_set():
                    break
                
                print(f"   Retrying: {movie['title']} (attempt {movie.get('retry_count', 0) + 1}/{self.max_retries})")
                self.queue_manager.move_failed_to_pending(movie)
    
    def _download_movie(self, movie: Dict):
        """
        Download a single movie with error handling
        
        Args:
            movie: Movie dictionary
        """
        title = movie.get('title', 'Unknown')
        
        # Check if already downloaded (fuzzy matching)
        if self._is_movie_downloaded(movie):
            print(f"\n✓ {title} - Already downloaded")
            self.queue_manager.add_to_completed(movie)
            return
        
        # Attempt download
        print(f"\n⬇️  Processing: {title}")
        success = self.downloader.download_movie(movie)
        
        if success:
            print(f"✓ Successfully downloaded: {title}")
            self.queue_manager.add_to_completed(movie)
        else:
            # Download failed - determine reason and calculate retry
            retry_count = movie.get('retry_count', 0)
            retry_after = self._calculate_retry_time(retry_count)
            
            error_msg = "Download failed - will retry"
            if retry_count >= self.max_retries - 1:
                error_msg = "Download failed - max retries reached"
            
            print(f"✗ {error_msg}: {title}")
            self.queue_manager.add_to_failed(movie, error_msg, retry_after)
    
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
        
        title = movie.get('title', '')
        year = movie.get('year', '')
        
        # Normalize title for matching
        normalized_title = title.lower().replace(' ', '.').replace(':', '').replace("'", '')
        
        # Search through files
        threshold = 0.85  # 85% similarity required
        
        for file_path in self.download_dir.rglob('*'):
            if not file_path.is_file():
                continue
            
            filename = file_path.stem.lower()
            
            # Calculate similarity
            similarity = SequenceMatcher(None, normalized_title, filename).ratio()
            
            # Bonus for year match
            if year and str(year) in filename:
                similarity += 0.10
            
            if similarity >= threshold:
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
        print("🛑 Stopping download worker...")
        self.stop_event.set()


if __name__ == "__main__":
    print("Worker Threads Test")
    print("=" * 60)
    print("This module should be run via main.py, not directly.")
    print("Use: python main.py --threaded")
