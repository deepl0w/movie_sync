"""
Queue Manager for Movie Sync
Handles communication between monitor and download threads using queues
Manages pending, failed, and retry queues with JSON persistence
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

# Module logger
logger = logging.getLogger(__name__)


class QueueManager:
    """Thread-safe queue manager for movie download orchestration"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize queue manager
        
        Args:
            config_dir: Directory for queue files (defaults to ~/.movie_sync)
        """
        if config_dir is None:
            config_dir = os.path.expanduser("~/.movie_sync")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Queue files
        self.pending_file = self.config_dir / "queue_pending.json"
        self.failed_file = self.config_dir / "queue_failed.json"
        self.completed_file = self.config_dir / "queue_completed.json"
        self.removed_file = self.config_dir / "queue_removed.json"
        
        # Thread locks for safe access
        self.pending_lock = threading.Lock()
        self.failed_lock = threading.Lock()
        self.completed_lock = threading.Lock()
        self.removed_lock = threading.Lock()
        
        # In-memory queues
        self.pending_queue: List[Dict] = []
        self.failed_queue: List[Dict] = []
        self.completed_queue: List[Dict] = []
        self.removed_queue: List[Dict] = []
        
        # Load existing queues from disk
        self._load_queues()
    
    def _load_queues(self) -> None:
        """Load all queues from disk"""
        self.pending_queue = self._load_json(self.pending_file, [])
        self.failed_queue = self._load_json(self.failed_file, [])
        self.completed_queue = self._load_json(self.completed_file, [])
        self.removed_queue = self._load_json(self.removed_file, [])
        
        logger.info(f"[QUEUE] Loaded queues: {len(self.pending_queue)} pending, "
              f"{len(self.failed_queue)} failed, {len(self.completed_queue)} completed, "
              f"{len(self.removed_queue)} removed")
    
    def _load_json(self, filepath: Path, default: List) -> List:
        """Load JSON file, return default if not found or invalid"""
        if not filepath.exists():
            return default
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[WARNING] Error loading {filepath.name}: {e}")
            return default
    
    def _save_json(self, filepath: Path, data: List) -> None:
        """Save data to JSON file atomically"""
        try:
            # Write to temporary file first
            temp_file = filepath.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_file.replace(filepath)
        except Exception as e:
            logger.error(f"[WARNING] Error saving {filepath.name}: {e}")
    
    # === PENDING QUEUE OPERATIONS ===
    
    def add_to_pending(self, movie: Dict) -> bool:
        """
        Add movie to pending queue if not already present
        
        Args:
            movie: Movie dictionary with at least 'id' and 'title'
            
        Returns:
            True if added, False if already exists
        """
        with self.pending_lock:
            # Check if already in pending queue
            if any(m.get('id') == movie.get('id') for m in self.pending_queue):
                return False
            
            # Check if already completed
            if any(m.get('id') == movie.get('id') for m in self.completed_queue):
                return False
            
            # Add timestamp and status
            movie['queued_at'] = int(time.time())
            movie['status'] = 'pending'
            
            self.pending_queue.append(movie)
            self._save_json(self.pending_file, self.pending_queue)
            return True
    
    def get_next_pending(self) -> Optional[Dict]:
        """
        Get and remove next movie from pending queue
        
        Returns:
            Movie dict or None if queue is empty
        """
        with self.pending_lock:
            if not self.pending_queue:
                return None
            
            movie = self.pending_queue.pop(0)
            self._save_json(self.pending_file, self.pending_queue)
            return movie
    
    def get_pending_count(self) -> int:
        """Get number of movies in pending queue"""
        with self.pending_lock:
            return len(self.pending_queue)
    
    # === FAILED QUEUE OPERATIONS ===
    
    def add_to_failed(self, movie: Dict, error: str, retry_after: Optional[int] = None) -> None:
        """
        Add movie to failed queue with retry information
        
        Args:
            movie: Movie dictionary
            error: Error message/reason for failure
            retry_after: Unix timestamp when to retry (None = immediate)
        """
        with self.failed_lock:
            # Check if already in failed queue
            existing = next((m for m in self.failed_queue if m.get('id') == movie.get('id')), None)
            
            if existing:
                # Update existing entry
                existing['retry_count'] = existing.get('retry_count', 0) + 1
                existing['last_error'] = error
                existing['last_failed_at'] = int(time.time())
                if retry_after:
                    existing['retry_after'] = retry_after
            else:
                # Add new failed entry - preserve retry_count if this is a re-failure
                movie['status'] = 'failed'
                movie['retry_count'] = movie.get('retry_count', 0) + 1
                movie['last_error'] = error
                movie['last_failed_at'] = int(time.time())
                if retry_after:
                    movie['retry_after'] = retry_after
                
                self.failed_queue.append(movie)
            
            self._save_json(self.failed_file, self.failed_queue)
    
    def get_movies_ready_for_retry(self, max_retries: int = 5) -> List[Dict]:
        """
        Get movies from failed queue that are ready to retry
        
        Args:
            max_retries: Maximum number of retries before giving up
            
        Returns:
            List of movies ready for retry
        """
        with self.failed_lock:
            current_time = int(time.time())
            ready_movies = []
            
            for movie in self.failed_queue:
                # Skip if exceeded max retries
                if movie.get('retry_count', 0) >= max_retries:
                    continue
                
                # Check if retry time has passed
                retry_after = movie.get('retry_after', 0)
                if current_time >= retry_after:
                    ready_movies.append(movie)
            
            return ready_movies
    
    def move_failed_to_pending(self, movie: Dict) -> None:
        """Move a movie from failed queue back to pending for retry"""
        with self.failed_lock:
            # Remove from failed queue
            self.failed_queue = [m for m in self.failed_queue if m.get('id') != movie.get('id')]
            self._save_json(self.failed_file, self.failed_queue)
        
        # Add to pending queue
        movie['status'] = 'pending'
        movie['retry_attempt'] = movie.get('retry_count', 0)
        with self.pending_lock:
            self.pending_queue.append(movie)
            self._save_json(self.pending_file, self.pending_queue)
    
    def get_failed_count(self) -> int:
        """Get number of movies in failed queue"""
        with self.failed_lock:
            return len(self.failed_queue)
    
    def get_permanent_failures(self, max_retries: int = 5) -> List[Dict]:
        """Get movies that have permanently failed (exceeded max retries)"""
        with self.failed_lock:
            return [m for m in self.failed_queue if m.get('retry_count', 0) >= max_retries]
    
    # === COMPLETED QUEUE OPERATIONS ===
    
    def add_to_completed(self, movie: Dict) -> None:
        """Mark movie as successfully completed"""
        with self.completed_lock:
            # Remove from failed queue if present
            with self.failed_lock:
                self.failed_queue = [m for m in self.failed_queue if m.get('id') != movie.get('id')]
                self._save_json(self.failed_file, self.failed_queue)
            
            # Check if already completed
            if any(m.get('id') == movie.get('id') for m in self.completed_queue):
                return
            
            movie['status'] = 'completed'
            movie['completed_at'] = int(time.time())
            
            self.completed_queue.append(movie)
            self._save_json(self.completed_file, self.completed_queue)
    
    def is_completed(self, movie_id: str) -> bool:
        """Check if movie has been completed"""
        with self.completed_lock:
            return any(m.get('id') == movie_id for m in self.completed_queue)
    
    def get_completed_count(self) -> int:
        """Get number of completed movies"""
        with self.completed_lock:
            return len(self.completed_queue)
    
    # === STATISTICS & MONITORING ===
    
    def get_statistics(self) -> Dict:
        """Get queue statistics"""
        return {
            'pending': self.get_pending_count(),
            'failed': self.get_failed_count(),
            'completed': self.get_completed_count(),
            'removed': self.get_removed_count(),
            'permanent_failures': len(self.get_permanent_failures())
        }
    
    def cleanup_old_completed(self, days: int = 30) -> int:
        """
        Remove completed entries older than specified days
        
        Args:
            days: Number of days to keep completed entries
            
        Returns:
            Number of entries removed
        """
        cutoff_time = int(time.time()) - (days * 24 * 60 * 60)
        
        with self.completed_lock:
            original_count = len(self.completed_queue)
            self.completed_queue = [
                m for m in self.completed_queue
                if m.get('completed_at', 0) > cutoff_time
            ]
            self._save_json(self.completed_file, self.completed_queue)
            
            removed = original_count - len(self.completed_queue)
            if removed > 0:
                logger.info(f"[CLEANUP] Cleaned up {removed} old completed entries")
            return removed
    
    def reset_failed_movie(self, movie_id: str) -> bool:
        """
        Manually reset a failed movie to pending
        
        Args:
            movie_id: ID of the movie to reset
            
        Returns:
            True if movie was found and reset
        """
        with self.failed_lock:
            movie = next((m for m in self.failed_queue if m.get('id') == movie_id), None)
            if not movie:
                return False
            
            self.failed_queue = [m for m in self.failed_queue if m.get('id') != movie_id]
            self._save_json(self.failed_file, self.failed_queue)
        
        # Reset retry count and add to pending
        movie['retry_count'] = 0
        movie.pop('last_error', None)
        movie.pop('retry_after', None)
        self.add_to_pending(movie)
        return True
    
    # === REMOVED QUEUE OPERATIONS ===
    
    def add_to_removed(self, movie: Dict) -> bool:
        """
        Add movie to removed queue (for movies no longer in watchlist)
        
        Args:
            movie: Movie dictionary
            
        Returns:
            True if added, False if already exists
        """
        with self.removed_lock:
            # Check if already in removed queue
            if any(m.get('id') == movie.get('id') for m in self.removed_queue):
                return False
            
            # Add timestamp
            movie['removed_at'] = int(time.time())
            movie['status'] = 'removed'
            
            self.removed_queue.append(movie)
            self._save_json(self.removed_file, self.removed_queue)
            return True
    
    def get_movies_ready_for_deletion(self, grace_period: int = 604800) -> List[Dict]:
        """
        Get movies from removed queue that are ready for deletion
        
        Args:
            grace_period: Grace period in seconds (default: 7 days)
            
        Returns:
            List of movies ready for deletion
        """
        with self.removed_lock:
            current_time = int(time.time())
            ready_movies = []
            
            for movie in self.removed_queue:
                removed_at = movie.get('removed_at', 0)
                if current_time >= (removed_at + grace_period):
                    ready_movies.append(movie)
            
            return ready_movies
    
    def remove_from_removed_queue(self, movie_id: str) -> bool:
        """
        Remove a movie from the removed queue (after deletion or restoration)
        
        Args:
            movie_id: ID of the movie to remove
            
        Returns:
            True if movie was found and removed
        """
        with self.removed_lock:
            original_len = len(self.removed_queue)
            self.removed_queue = [m for m in self.removed_queue if m.get('id') != movie_id]
            
            if len(self.removed_queue) < original_len:
                self._save_json(self.removed_file, self.removed_queue)
                return True
            return False
    
    def mark_movies_as_removed(self, current_watchlist_ids: List[str]) -> int:
        """
        Mark movies as removed if they're no longer in the watchlist
        Checks completed movies and moves them to removed queue if not in watchlist
        
        Args:
            current_watchlist_ids: List of movie IDs currently in watchlist
            
        Returns:
            Number of movies marked as removed
        """
        removed_count = 0
        current_watchlist_set = set(current_watchlist_ids)
        
        # Check completed movies
        with self.completed_lock:
            movies_to_remove = []
            for movie in self.completed_queue:
                if movie.get('id') not in current_watchlist_set:
                    movies_to_remove.append(movie)
            
            # Remove from completed queue
            for movie in movies_to_remove:
                self.completed_queue = [m for m in self.completed_queue if m.get('id') != movie.get('id')]
                if self.add_to_removed(movie):
                    removed_count += 1
                    logger.info(f"[REMOVE] Marked for removal: {movie.get('title', 'Unknown')} (removed from watchlist)")
            
            if movies_to_remove:
                self._save_json(self.completed_file, self.completed_queue)
        
        # Also check pending queue and remove if not in watchlist
        with self.pending_lock:
            movies_to_remove = []
            for movie in self.pending_queue:
                if movie.get('id') not in current_watchlist_set:
                    movies_to_remove.append(movie)
            
            for movie in movies_to_remove:
                self.pending_queue = [m for m in self.pending_queue if m.get('id') != movie.get('id')]
                if self.add_to_removed(movie):
                    removed_count += 1
                    logger.info(f"[REMOVE] Marked for removal: {movie.get('title', 'Unknown')} (removed from watchlist)")
            
            if movies_to_remove:
                self._save_json(self.pending_file, self.pending_queue)
        
        return removed_count
    
    def get_removed_count(self) -> int:
        """Get number of movies in removed queue"""
        with self.removed_lock:
            return len(self.removed_queue)
    
    def restore_removed_movie(self, movie_id: str) -> bool:
        """
        Restore a removed movie back to pending queue
        (useful if movie was re-added to watchlist)
        
        Args:
            movie_id: ID of the movie to restore
            
        Returns:
            True if movie was found and restored
        """
        with self.removed_lock:
            movie = next((m for m in self.removed_queue if m.get('id') == movie_id), None)
            if not movie:
                return False
            
            self.removed_queue = [m for m in self.removed_queue if m.get('id') != movie_id]
            self._save_json(self.removed_file, self.removed_queue)
        
        # Add back to pending
        movie['status'] = 'pending'
        movie.pop('removed_at', None)
        self.add_to_pending(movie)
        return True
