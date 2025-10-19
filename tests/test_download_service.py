"""Tests for DownloadService"""

import pytest
import json
import time
from pathlib import Path

from download_service import MovieDownloader


class TestMovieDownloader:
    """Test cases for the MovieDownloader base class"""
    
    def test_initialization(self, temp_dir):
        """Test downloader initialization"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        assert downloader.queue_file == str(queue_file)
        assert downloader.queue == []
    
    def test_load_existing_queue(self, temp_dir, sample_watchlist):
        """Test loading existing queue from file"""
        queue_file = temp_dir / "queue.json"
        
        # Create queue file
        queue_data = [
            {**sample_watchlist[0], "status": "pending", "queued_at": int(time.time())}
        ]
        with open(queue_file, 'w') as f:
            json.dump(queue_data, f)
        
        downloader = MovieDownloader(str(queue_file))
        
        assert len(downloader.queue) == 1
        assert downloader.queue[0]["id"] == sample_watchlist[0]["id"]
        assert downloader.queue[0]["status"] == "pending"
    
    def test_load_nonexistent_queue(self, temp_dir):
        """Test loading queue when file doesn't exist"""
        queue_file = temp_dir / "nonexistent.json"
        downloader = MovieDownloader(str(queue_file))
        
        assert downloader.queue == []
    
    def test_load_corrupted_queue(self, temp_dir, caplog):
        """Test loading corrupted queue file"""
        queue_file = temp_dir / "corrupted.json"
        queue_file.write_text("invalid json {{{")
        
        downloader = MovieDownloader(str(queue_file))
        
        assert downloader.queue == []
        assert "Error loading" in caplog.text
    
    def test_save_queue(self, temp_dir, sample_movie):
        """Test saving queue to file"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        # Add to queue and save
        downloader.queue = [
            {**sample_movie, "status": "pending", "queued_at": int(time.time())}
        ]
        downloader._save_queue()
        
        # Verify file was created
        assert queue_file.exists()
        
        # Verify content
        with open(queue_file, 'r') as f:
            saved_queue = json.load(f)
        
        assert len(saved_queue) == 1
        assert saved_queue[0]["id"] == sample_movie["id"]
    
    def test_queue_movie(self, temp_dir, sample_movie):
        """Test adding a movie to the queue"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        # Mock process_downloads to avoid actual processing
        downloader.process_downloads = lambda: None
        
        downloader.queue_movie(sample_movie)
        
        assert len(downloader.queue) == 1
        assert downloader.queue[0]["id"] == sample_movie["id"]
        assert downloader.queue[0]["status"] == "pending"
        assert "queued_at" in downloader.queue[0]
    
    def test_queue_movie_saves_to_file(self, temp_dir, sample_movie):
        """Test that queuing a movie saves to file"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        # Mock process_downloads
        downloader.process_downloads = lambda: None
        
        downloader.queue_movie(sample_movie)
        
        # Verify file was created
        assert queue_file.exists()
        
        # Verify can be loaded by another instance
        downloader2 = MovieDownloader(str(queue_file))
        assert len(downloader2.queue) == 1
        assert downloader2.queue[0]["id"] == sample_movie["id"]
    
    def test_queue_movie_calls_process_downloads(self, temp_dir, sample_movie, mocker):
        """Test that queuing a movie triggers download processing"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        # Spy on process_downloads
        process_spy = mocker.spy(downloader, 'process_downloads')
        
        downloader.queue_movie(sample_movie)
        
        process_spy.assert_called_once()
    
    def test_process_downloads_marks_as_downloaded(self, temp_dir, sample_movie):
        """Test that process_downloads marks movies as downloaded"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        # Add pending movie to queue
        downloader.queue = [
            {**sample_movie, "status": "pending", "queued_at": int(time.time())}
        ]
        
        # Mock download_movie to succeed
        downloader.download_movie = lambda movie: True
        
        downloader.process_downloads()
        
        assert downloader.queue[0]["status"] == "downloaded"
        assert "downloaded_at" in downloader.queue[0]
    
    def test_download_movie_placeholder(self, temp_dir, sample_movie, caplog):
        """Test that base download_movie is a placeholder"""
        queue_file = temp_dir / "queue.json"
        downloader = MovieDownloader(str(queue_file))
        
        result = downloader.download_movie(sample_movie)
        
        assert result is True
        assert "Downloading movie" in caplog.text
