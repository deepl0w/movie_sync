"""Tests for QueueManager"""

import pytest
import json
import time
from pathlib import Path

from queue_manager import QueueManager


class TestQueueManager:
    """Test cases for the QueueManager class"""
    
    def test_initialization(self, temp_dir):
        """Test queue manager initialization"""
        qm = QueueManager(str(temp_dir))
        
        assert qm.config_dir == temp_dir
        assert qm.pending_queue == []
        assert qm.failed_queue == []
        assert qm.completed_queue == []
    
    def test_add_to_pending(self, temp_dir):
        """Test adding movies to pending queue"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # First add should succeed
        assert qm.add_to_pending(movie) == True
        assert qm.get_pending_count() == 1
        
        # Second add should fail (duplicate)
        assert qm.add_to_pending(movie) == False
        assert qm.get_pending_count() == 1
    
    def test_get_next_pending(self, temp_dir):
        """Test getting movies from pending queue"""
        qm = QueueManager(str(temp_dir))
        
        movies = [
            {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999},
            {'id': 'tt0234215', 'title': 'The Matrix Reloaded', 'year': 2003}
        ]
        
        for movie in movies:
            qm.add_to_pending(movie)
        
        # Get first movie
        movie1 = qm.get_next_pending()
        assert movie1['id'] == 'tt0133093'
        assert qm.get_pending_count() == 1
        
        # Get second movie
        movie2 = qm.get_next_pending()
        assert movie2['id'] == 'tt0234215'
        assert qm.get_pending_count() == 0
        
        # Queue is empty
        movie3 = qm.get_next_pending()
        assert movie3 is None
    
    def test_add_to_failed(self, temp_dir):
        """Test adding movies to failed queue"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Add to failed queue
        qm.add_to_failed(movie, "Not found", retry_after=int(time.time()) + 3600)
        
        assert qm.get_failed_count() == 1
        assert qm.failed_queue[0]['retry_count'] == 1
        assert qm.failed_queue[0]['last_error'] == "Not found"
    
    def test_add_to_failed_increments_retry_count(self, temp_dir):
        """Test that adding same movie to failed queue increments retry count"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Add multiple times
        qm.add_to_failed(movie, "Error 1")
        qm.add_to_failed(movie, "Error 2")
        qm.add_to_failed(movie, "Error 3")
        
        assert qm.get_failed_count() == 1  # Still one entry
        assert qm.failed_queue[0]['retry_count'] == 3
        assert qm.failed_queue[0]['last_error'] == "Error 3"
    
    def test_get_movies_ready_for_retry(self, temp_dir):
        """Test getting movies ready for retry"""
        qm = QueueManager(str(temp_dir))
        
        current_time = int(time.time())
        
        # Movie ready now
        movie1 = {'id': 'tt0001', 'title': 'Ready Now', 'year': 2020}
        qm.add_to_failed(movie1, "Error", retry_after=current_time - 1)
        
        # Movie not ready yet
        movie2 = {'id': 'tt0002', 'title': 'Not Ready', 'year': 2020}
        qm.add_to_failed(movie2, "Error", retry_after=current_time + 3600)
        
        # Get ready movies
        ready = qm.get_movies_ready_for_retry()
        assert len(ready) == 1
        assert ready[0]['id'] == 'tt0001'
    
    def test_move_failed_to_pending(self, temp_dir):
        """Test moving movie from failed to pending"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        qm.add_to_failed(movie, "Error")
        
        assert qm.get_failed_count() == 1
        assert qm.get_pending_count() == 0
        
        qm.move_failed_to_pending(movie)
        
        assert qm.get_failed_count() == 0
        assert qm.get_pending_count() == 1
    
    def test_add_to_completed(self, temp_dir):
        """Test adding movies to completed queue"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        qm.add_to_completed(movie)
        
        assert qm.get_completed_count() == 1
        assert qm.is_completed('tt0133093') == True
        assert qm.is_completed('tt0000000') == False
    
    def test_completed_prevents_pending(self, temp_dir):
        """Test that completed movies can't be added to pending"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Add to completed
        qm.add_to_completed(movie)
        
        # Try to add to pending - should fail
        assert qm.add_to_pending(movie) == False
    
    def test_completed_removes_from_failed(self, temp_dir):
        """Test that marking as completed removes from failed queue"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Add to failed
        qm.add_to_failed(movie, "Error")
        assert qm.get_failed_count() == 1
        
        # Mark as completed
        qm.add_to_completed(movie)
        assert qm.get_failed_count() == 0
        assert qm.get_completed_count() == 1
    
    def test_get_permanent_failures(self, temp_dir):
        """Test getting permanently failed movies"""
        qm = QueueManager(str(temp_dir))
        
        movie1 = {'id': 'tt0001', 'title': 'Permanent Failure', 'year': 2020}
        movie2 = {'id': 'tt0002', 'title': 'Temporary Failure', 'year': 2020}
        
        # Add movie1 5 times (max retries)
        for i in range(5):
            qm.add_to_failed(movie1, f"Error {i+1}")
        
        # Add movie2 once
        qm.add_to_failed(movie2, "Error")
        
        # Get permanent failures
        permanent = qm.get_permanent_failures(max_retries=5)
        assert len(permanent) == 1
        assert permanent[0]['id'] == 'tt0001'
    
    def test_get_statistics(self, temp_dir):
        """Test getting queue statistics"""
        qm = QueueManager(str(temp_dir))
        
        # Add some movies
        qm.add_to_pending({'id': 'tt0001', 'title': 'Pending 1', 'year': 2020})
        qm.add_to_pending({'id': 'tt0002', 'title': 'Pending 2', 'year': 2020})
        qm.add_to_failed({'id': 'tt0003', 'title': 'Failed 1', 'year': 2020}, "Error")
        qm.add_to_completed({'id': 'tt0004', 'title': 'Completed 1', 'year': 2020})
        
        stats = qm.get_statistics()
        assert stats['pending'] == 2
        assert stats['failed'] == 1
        assert stats['completed'] == 1
        assert stats['permanent_failures'] == 0
    
    def test_persistence(self, temp_dir):
        """Test that queues are persisted to disk"""
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Create queue manager and add movie
        qm1 = QueueManager(str(temp_dir))
        qm1.add_to_pending(movie)
        
        # Create new instance - should load from disk
        qm2 = QueueManager(str(temp_dir))
        assert qm2.get_pending_count() == 1
        assert qm2.pending_queue[0]['id'] == 'tt0133093'
    
    def test_reset_failed_movie(self, temp_dir):
        """Test manually resetting a failed movie"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # Add to failed with high retry count
        for i in range(3):
            qm.add_to_failed(movie, f"Error {i+1}")
        
        assert qm.failed_queue[0]['retry_count'] == 3
        
        # Reset
        result = qm.reset_failed_movie('tt0133093')
        assert result == True
        assert qm.get_failed_count() == 0
        assert qm.get_pending_count() == 1
        
        # Check retry count was reset
        pending_movie = qm.get_next_pending()
        assert pending_movie.get('retry_count', 0) == 0
    
    def test_cleanup_old_completed(self, temp_dir):
        """Test cleanup of old completed entries"""
        qm = QueueManager(str(temp_dir))
        
        current_time = int(time.time())
        
        # Add old completed movie (40 days ago)
        old_movie = {'id': 'tt0001', 'title': 'Old Movie', 'year': 2020}
        qm.add_to_completed(old_movie)
        qm.completed_queue[0]['completed_at'] = current_time - (40 * 24 * 60 * 60)
        qm._save_json(qm.completed_file, qm.completed_queue)
        
        # Add recent completed movie
        recent_movie = {'id': 'tt0002', 'title': 'Recent Movie', 'year': 2020}
        qm.add_to_completed(recent_movie)
        
        # Cleanup (keep last 30 days)
        removed = qm.cleanup_old_completed(days=30)
        
        assert removed == 1
        assert qm.get_completed_count() == 1
        assert qm.completed_queue[0]['id'] == 'tt0002'
    
    def test_retry_count_increments_across_retries(self, temp_dir):
        """Test that retry_count properly increments when movie fails multiple times"""
        qm = QueueManager(str(temp_dir))
        
        movie = {'id': 'tt0133093', 'title': 'The Matrix', 'year': 1999}
        
        # First failure
        qm.add_to_failed(movie, "Download failed", retry_after=int(time.time()))
        assert qm.get_failed_count() == 1
        failed_movie = qm.failed_queue[0]
        assert failed_movie['retry_count'] == 1
        
        # Move to pending for retry
        qm.move_failed_to_pending(failed_movie.copy())
        assert qm.get_failed_count() == 0
        assert qm.get_pending_count() == 1
        
        # Get the movie from pending (it still has retry_count)
        pending_movie = qm.pending_queue[0]
        assert pending_movie['retry_count'] == 1
        
        # Second failure - retry_count should increment to 2
        qm.add_to_failed(pending_movie, "Download failed again", retry_after=int(time.time()))
        assert qm.get_failed_count() == 1
        failed_movie = qm.failed_queue[0]
        assert failed_movie['retry_count'] == 2
        
        # Move to pending again
        qm.move_failed_to_pending(failed_movie.copy())
        pending_movie = qm.pending_queue[0]
        assert pending_movie['retry_count'] == 2
        
        # Third failure - retry_count should increment to 3
        qm.add_to_failed(pending_movie, "Download failed yet again", retry_after=int(time.time()))
        assert qm.get_failed_count() == 1
        failed_movie = qm.failed_queue[0]
        assert failed_movie['retry_count'] == 3

