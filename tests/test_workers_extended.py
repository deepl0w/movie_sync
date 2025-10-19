"""Extended tests for workers.py - additional coverage"""

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from workers import MonitorWorker, DownloadWorker, CleanupWorker
from queue_manager import QueueManager


@pytest.fixture
def mock_monitor():
    """Create a mock Letterboxd monitor"""
    monitor = MagicMock()
    monitor.check_for_new_movies.return_value = []
    return monitor


@pytest.fixture
def mock_queue():
    """Create a mock queue manager"""
    queue = MagicMock()
    queue.pending_queue = []
    queue.failed_queue = []
    queue.completed_queue = []
    queue.removed_queue = []
    queue.get_next_pending.return_value = None
    queue.get_retry_candidates.return_value = []
    return queue


@pytest.fixture
def mock_downloader():
    """Create a mock downloader"""
    downloader = MagicMock()
    downloader.download_movie.return_value = True
    return downloader


@pytest.fixture
def mock_cleanup_service():
    """Create a mock cleanup service"""
    service = MagicMock()
    service.cleanup_movie.return_value = {
        'files_deleted': True,
        'torrent_deleted': True,
        'qbt_removed': True,
        'errors': []
    }
    return service


class TestMonitorWorkerExtended:
    """Extended tests for MonitorWorker"""
    
    def test_monitor_worker_stop(self, mock_queue):
        """Test stopping MonitorWorker"""
        worker = MonitorWorker("testuser", mock_queue, check_interval=1)
        worker.stop()
        
        assert worker.stop_event.is_set()
    
    def test_monitor_worker_reload_config(self, mock_queue):
        """Test reloading MonitorWorker config"""
        worker = MonitorWorker("testuser", mock_queue, check_interval=300)
        
        new_config = {'check_interval': 600}
        worker.reload_config(new_config)
        
        assert worker.check_interval == 600


class TestDownloadWorkerExtended:
    """Extended tests for DownloadWorker"""
    
    def test_download_worker_init(self, mock_queue, mock_downloader, temp_dir):
        """Test DownloadWorker initialization"""
        worker = DownloadWorker(
            mock_queue, 
            mock_downloader,
            str(temp_dir),
            retry_interval=3600,
            max_retries=5,
            backoff_multiplier=2.0,
            max_download_space_gb=100
        )
        
        assert worker.queue_manager == mock_queue
        assert worker.downloader == mock_downloader
        assert worker.retry_interval == 3600
        assert worker.max_retries == 5
        assert worker.backoff_multiplier == 2.0
        assert worker.max_download_space_gb == 100
        assert worker.running is False
    
    def test_download_worker_stop(self, mock_queue, mock_downloader, temp_dir):
        """Test stopping DownloadWorker"""
        worker = DownloadWorker(mock_queue, mock_downloader, str(temp_dir))
        worker.stop()
        
        assert worker.stop_event.is_set()
    
    def test_download_worker_calculate_retry_time(self, mock_queue, mock_downloader, temp_dir):
        """Test exponential backoff calculation"""
        import time
        
        worker = DownloadWorker(
            mock_queue, 
            mock_downloader, 
            str(temp_dir),
            retry_interval=3600,
            backoff_multiplier=2.0
        )
        
        # Test retry times with exponential backoff
        now = int(time.time())
        
        retry1 = worker._calculate_retry_time(0)
        assert retry1 >= now + 3600  # At least 1 hour from now
        assert retry1 <= now + 3700  # Give some buffer
        
        retry2 = worker._calculate_retry_time(1)
        assert retry2 >= now + 7200  # At least 2 hours from now
        assert retry2 <= now + 7300  # Give some buffer
        
        retry3 = worker._calculate_retry_time(2)
        assert retry3 >= now + 14400  # At least 4 hours from now
        assert retry3 <= now + 14500  # Give some buffer
    
    def test_download_worker_is_movie_downloaded(self, mock_queue, mock_downloader, temp_dir):
        """Test fuzzy matching for downloaded movies"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        # Create a downloaded movie file
        movie_file = download_dir / "Inception.2010.1080p.BluRay.mkv"
        movie_file.write_text("fake movie")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {'title': 'Inception', 'year': '2010'}
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_download_worker_is_movie_not_downloaded(self, mock_queue, mock_downloader, temp_dir):
        """Test when movie is not downloaded"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {'title': 'Inception', 'year': '2010'}
        result = worker._is_movie_downloaded(movie)
        
        assert result is False
    
    def test_download_worker_force_download_clears_flag(self, mock_queue, mock_downloader, temp_dir, mocker):
        """Test that force_download flag is cleared after processing"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        worker._is_movie_downloaded = mocker.MagicMock(return_value=False)
        worker._check_space_available = mocker.MagicMock(return_value=False)  # Space limit
        
        movie = {
            'title': 'Test Movie',
            'year': 2020,
            'id': 'test123',
            'force_download': True
        }
        
        worker._download_movie(movie)
        
        # force_download flag should be cleared
        assert movie.get('force_download') is False
    
    def test_download_worker_process_retries(self, mock_queue, mock_downloader, temp_dir):
        """Test processing retry candidates"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        # Create retry candidates
        retry_movies = [
            {'id': '1', 'title': 'Movie 1', 'year': 2020, 'retry_count': 1},
            {'id': '2', 'title': 'Movie 2', 'year': 2021, 'retry_count': 2}
        ]
        mock_queue.get_movies_ready_for_retry.return_value = retry_movies
        mock_queue.move_failed_to_pending = MagicMock()
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir), max_retries=5)
        worker._process_retries()
        
        # Verify retries were moved back to pending
        assert mock_queue.move_failed_to_pending.call_count == 2
    
    def test_download_worker_skip_on_unexpected_error(self, mock_queue, mock_downloader, temp_dir, mocker):
        """Test handling of unexpected errors during download"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        # Mock _is_movie_downloaded to raise exception
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        worker._is_movie_downloaded = mocker.MagicMock(side_effect=Exception("Unexpected error"))
        
        mock_queue.add_to_failed = MagicMock()
        mock_queue.get_next_pending.side_effect = [
            {'id': '1', 'title': 'Test Movie', 'year': 2020},
            None
        ]
        
        worker._process_pending_movies()
        
        # Verify movie was added to failed queue with error
        mock_queue.add_to_failed.assert_called_once()
        call_args = mock_queue.add_to_failed.call_args[0]
        assert 'Unexpected error' in call_args[1]
    
    def test_download_worker_skip_already_downloaded(self, mock_queue, mock_downloader, temp_dir, mocker):
        """Test skipping already downloaded movies"""
        download_dir = Path(temp_dir) / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        worker._is_movie_downloaded = mocker.MagicMock(return_value=True)
        mock_queue.add_to_completed = MagicMock()
        
        movie = {'id': '1', 'title': 'Test Movie', 'year': 2020}
        worker._download_movie(movie)
        
        # Verify movie was moved to completed without downloading
        mock_queue.add_to_completed.assert_called_once_with(movie)
        mock_downloader.download_movie.assert_not_called()


class TestCleanupWorkerExtended:
    """Extended tests for CleanupWorker"""
    
    def test_cleanup_worker_init(self, mock_queue, mock_cleanup_service):
        """Test CleanupWorker initialization"""
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            check_interval=3600,
            grace_period=86400,
            enabled=True
        )
        
        assert worker.queue_manager == mock_queue
        assert worker.cleanup_service == mock_cleanup_service
        assert worker.grace_period == 86400
        assert worker.check_interval == 3600
        assert worker.enabled is True
        assert worker.running is False
    
    def test_cleanup_worker_stop(self, mock_queue, mock_cleanup_service):
        """Test stopping CleanupWorker"""
        worker = CleanupWorker(mock_queue, mock_cleanup_service)
        worker.stop()
        
        assert worker.stop_event.is_set()
    
    def test_cleanup_worker_reload_config(self, mock_queue, mock_cleanup_service):
        """Test reloading CleanupWorker config"""
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,
            check_interval=3600,
            enabled=False
        )
        
        new_config = {
            'removal_grace_period': 172800,  # 2 days
            'enable_removal_cleanup': True
        }
        worker.reload_config(new_config)
        
        assert worker.grace_period == 172800
        assert worker.enabled is True
        # Note: check_interval is not reloadable in current implementation
    
    def test_cleanup_worker_process_removals_within_grace(self, mock_queue, mock_cleanup_service):
        """Test that movies within grace period are not cleaned"""
        import time
        
        # Movie just added (within grace period)
        recent_movie = {
            'id': '1',
            'title': 'Recent Movie',
            'year': 2020,
            'removed_at': time.time()
        }
        mock_queue.removed_queue = [recent_movie]
        
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,  # 1 day
            enabled=True
        )
        
        worker._process_removals()
        
        # Should not cleanup yet
        mock_cleanup_service.cleanup_movie.assert_not_called()
    
    def test_cleanup_worker_process_removals_after_grace(self, mock_queue, mock_cleanup_service):
        """Test that movies after grace period are cleaned"""
        import time
        
        # Movie added 2 days ago (beyond grace period)
        old_movie = {
            'id': '1',
            'title': 'Old Movie',
            'year': 2020,
            'removed_at': time.time() - (2 * 86400)  # 2 days ago
        }
        
        # Mock queue_manager.get_movies_ready_for_deletion to return old movie
        mock_queue.get_movies_ready_for_deletion = MagicMock(return_value=[old_movie])
        mock_queue.remove_from_removed_queue = MagicMock()
        
        # Mock cleanup_service.cleanup_movie to return success
        mock_cleanup_service.cleanup_movie.return_value = {
            'files_deleted': True,
            'torrent_deleted': True,
            'qbt_removed': True,
            'errors': []
        }
        
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,  # 1 day
            enabled=True
        )
        
        worker._process_removals()
        
        # Should cleanup
        mock_cleanup_service.cleanup_movie.assert_called_once_with(
            old_movie,
            delete_files=True,
            delete_torrent=True,
            remove_from_qbt=True
        )
        # Should remove from queue after successful cleanup
        mock_queue.remove_from_removed_queue.assert_called_once_with('1')
        mock_queue.remove_from_removed_queue.assert_called_once_with('1')
    
    def test_cleanup_worker_process_removals_no_timestamp(self, mock_queue, mock_cleanup_service):
        """Test handling movies without removed_at timestamp"""
        # Movie without timestamp (should use current time)
        movie_no_timestamp = {
            'id': '1',
            'title': 'No Timestamp Movie',
            'year': 2020
        }
        mock_queue.removed_queue = [movie_no_timestamp]
        
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,
            enabled=True
        )
        
        worker._process_removals()
        
        # Should not cleanup (treated as recent)
        mock_cleanup_service.cleanup_movie.assert_not_called()
    
    def test_cleanup_worker_cleanup_error_handling(self, mock_queue, mock_cleanup_service):
        """Test error handling during cleanup"""
        import time
        
        old_movie = {
            'id': '1',
            'title': 'Error Movie',
            'year': 2020,
            'removed_at': time.time() - (2 * 86400)
        }
        mock_queue.removed_queue = [old_movie]
        mock_queue.remove_from_removed = MagicMock()
        
        # Mock cleanup to raise error
        mock_cleanup_service.cleanup_movie.side_effect = Exception("Cleanup failed")
        
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,
            enabled=True
        )
        
        # Should not crash
        worker._process_removals()
        
        # Movie should remain in removed queue
        assert old_movie in mock_queue.removed_queue
    
    def test_cleanup_worker_disabled(self, mock_queue, mock_cleanup_service):
        """Test that cleanup is skipped when disabled"""
        import time
        
        old_movie = {
            'id': '1',
            'title': 'Old Movie',
            'year': 2020,
            'removed_at': time.time() - (2 * 86400)
        }
        mock_queue.removed_queue = [old_movie]
        
        worker = CleanupWorker(
            mock_queue,
            mock_cleanup_service,
            grace_period=86400,
            enabled=False  # Disabled
        )
        
        worker._process_removals()
        
        # Should not cleanup when disabled
        mock_cleanup_service.cleanup_movie.assert_not_called()


class TestWorkerIntegration:
    """Integration tests for worker interactions"""
    
    def test_worker_thread_lifecycle(self, mock_queue, mock_monitor):
        """Test worker starts and stops properly"""
        worker = MonitorWorker(mock_queue, mock_monitor, check_interval=1)
        
        # Start worker
        worker.start()
        assert worker.is_alive()
        
        # Let it run briefly
        time.sleep(0.2)
        
        # Stop worker
        worker.stop()
        worker.join(timeout=2)
        
        assert not worker.is_alive()
    
    def test_multiple_workers_can_run(self, mock_queue, mock_monitor, mock_downloader, mock_cleanup_service, temp_dir):
        """Test multiple workers can run simultaneously"""
        monitor_worker = MonitorWorker(mock_queue, mock_monitor, check_interval=1)
        download_worker = DownloadWorker(mock_queue, mock_downloader, str(temp_dir))
        cleanup_worker = CleanupWorker(mock_queue, mock_cleanup_service, check_interval=1, enabled=False)
        
        # Start all workers
        monitor_worker.start()
        download_worker.start()
        cleanup_worker.start()
        
        time.sleep(0.2)
        
        # All should be running
        assert monitor_worker.is_alive()
        assert download_worker.is_alive()
        assert cleanup_worker.is_alive()
        
        # Stop all
        monitor_worker.stop()
        download_worker.stop()
        cleanup_worker.stop()
        
        monitor_worker.join(timeout=2)
        download_worker.join(timeout=2)
        cleanup_worker.join(timeout=2)
        
        assert not monitor_worker.is_alive()
        assert not download_worker.is_alive()
        assert not cleanup_worker.is_alive()
