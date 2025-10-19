"""Tests for Workers"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from workers import MonitorWorker, DownloadWorker, get_directory_size_gb


class TestUtilityFunctions:
    """Test cases for utility functions"""
    
    def test_get_directory_size_gb_empty(self, temp_dir):
        """Test calculating size of empty directory"""
        test_dir = temp_dir / "empty"
        test_dir.mkdir()
        
        size = get_directory_size_gb(test_dir)
        assert size == 0.0
    
    def test_get_directory_size_gb_with_files(self, temp_dir):
        """Test calculating size of directory with files"""
        test_dir = temp_dir / "files"
        test_dir.mkdir()
        
        # Create files with known sizes
        (test_dir / "file1.txt").write_text("x" * 1024)  # 1 KB
        (test_dir / "file2.txt").write_text("x" * 2048)  # 2 KB
        
        size = get_directory_size_gb(test_dir)
        # 3 KB = 3072 bytes = 0.000002861 GB approximately
        assert size > 0
        assert size < 0.001  # Should be very small
    
    def test_get_directory_size_gb_nonexistent(self, temp_dir):
        """Test calculating size of non-existent directory"""
        test_dir = temp_dir / "nonexistent"
        
        size = get_directory_size_gb(test_dir)
        assert size == 0.0
    
    def test_get_directory_size_gb_nested(self, temp_dir):
        """Test calculating size of directory with nested files"""
        test_dir = temp_dir / "nested"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()
        
        # Create files in both directories
        (test_dir / "file1.txt").write_text("x" * 1000)
        (subdir / "file2.txt").write_text("x" * 2000)
        
        size = get_directory_size_gb(test_dir)
        # Should include both files
        assert size > 0


class TestMonitorWorkerFuzzyMatching:
    """Test cases for fuzzy matching in DownloadWorker"""
    
    def test_is_movie_downloaded_exact_match(self, temp_dir, mocker):
        """Test detecting downloaded movie with exact substring match"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Enter.the.Void.2009.1080p.BluRay.DD5.1.x264-DON.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Enter the Void',
            'year': 2009
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_fuzzy_match(self, temp_dir, mocker):
        """Test detecting downloaded movie with fuzzy matching"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file with additional text
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Blade.Runner.1982.Directors.Cut.1080p.BluRay.x264.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Blade Runner',
            'year': 1982
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_not_found(self, temp_dir, mocker):
        """Test when movie is not downloaded"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file for different movie
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Heat.1995.1080p.BluRay.DTS.x264-HiDt.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Blade Runner',
            'year': 1982
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is False
    
    def test_is_movie_downloaded_year_mismatch(self, temp_dir, mocker):
        """Test that year mismatch prevents match"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Heat.1995.1080p.BluRay.DTS.x264-HiDt.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Heat',
            'year': 2020  # Wrong year
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is False
    
    def test_is_movie_downloaded_special_characters(self, temp_dir, mocker):
        """Test detecting movie with special characters in title"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Moulin.Rouge.2001.1080p.BluRay.x264.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Moulin Rouge!',  # Has exclamation mark
            'year': 2001
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_no_year(self, temp_dir, mocker):
        """Test detecting movie when year is not specified"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "2046.2004.1080p.BluRay.x264-CiNEFiLE.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': '2046',
            'year': None  # No year specified
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_nested_directory(self, temp_dir, mocker):
        """Test detecting movie in nested directory structure"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file in nested directory
        download_dir = temp_dir / "downloads"
        nested_dir = download_dir / "Enter.the.Void.2009.1080p.BluRay.DD5.1.x264-DON"
        nested_dir.mkdir(parents=True)
        movie_file = nested_dir / "Enter.the.Void.2009.1080p.BluRay.DD5.1.x264-DON.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Enter the Void',
            'year': 2009
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_empty_directory(self, temp_dir, mocker):
        """Test when download directory is empty"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create empty download directory
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Enter the Void',
            'year': 2009
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is False
    
    def test_is_movie_downloaded_numeric_title(self, temp_dir, mocker):
        """Test detecting movie with numeric title"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "2046.2004.1080p.BluRay.x264-CiNEFiLE.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': '2046',
            'year': 2004
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True
    
    def test_is_movie_downloaded_with_colon(self, temp_dir, mocker):
        """Test detecting movie with colon in title"""
        # Mock dependencies
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        # Create test movie file (colons typically replaced in filenames)
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        movie_file = download_dir / "Blade.Trinity.2004.1080p.BluRay.x264.mkv"
        movie_file.write_text("fake movie content")
        
        worker = DownloadWorker(mock_queue, mock_downloader, str(download_dir))
        
        movie = {
            'title': 'Blade: Trinity',  # Has colon
            'year': 2004
        }
        
        result = worker._is_movie_downloaded(movie)
        
        assert result is True


class TestDownloadSpaceLimit:
    """Test cases for download space limit functionality"""
    
    def test_check_space_available_unlimited(self, temp_dir, mocker):
        """Test space check when limit is disabled (0)"""
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(
            mock_queue, mock_downloader, str(download_dir),
            max_download_space_gb=0  # Unlimited
        )
        
        assert worker._check_space_available() is True
    
    def test_check_space_available_under_limit(self, temp_dir, mocker):
        """Test space check when under the limit"""
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        # Create a small file (much less than 10 GB)
        test_file = download_dir / "test.mkv"
        test_file.write_text("small file")
        
        worker = DownloadWorker(
            mock_queue, mock_downloader, str(download_dir),
            max_download_space_gb=10  # 10 GB limit
        )
        
        assert worker._check_space_available() is True
    
    def test_check_space_available_over_limit(self, temp_dir, mocker):
        """Test space check when over the limit"""
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(
            mock_queue, mock_downloader, str(download_dir),
            max_download_space_gb=0.00000001  # Very tiny limit (10 bytes)
        )
        
        # Create a file that exceeds the tiny limit
        test_file = download_dir / "large.mkv"
        test_file.write_text("x" * 1000)  # 1 KB, way over 10 byte limit
        
        assert worker._check_space_available() is False
    
    def test_download_movie_skips_when_space_limit_reached(self, temp_dir, mocker):
        """Test that download is skipped when space limit is reached"""
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        # Create a file to use up space
        test_file = download_dir / "existing.mkv"
        test_file.write_text("x" * 1000)
        
        worker = DownloadWorker(
            mock_queue, mock_downloader, str(download_dir),
            max_download_space_gb=0.00000001  # Tiny limit (10 bytes)
        )
        
        movie = {
            'title': 'Test Movie',
            'year': 2020,
            'id': 'test123'
        }
        
        # Mock the _is_movie_downloaded to return False
        worker._is_movie_downloaded = mocker.MagicMock(return_value=False)
        
        worker._download_movie(movie)
        
        # Verify movie was moved to failed queue with space limit reason
        assert mock_queue.add_to_failed.called
        call_args = mock_queue.add_to_failed.call_args
        assert call_args[0][0]['failed_reason'] == 'space_limit'
        assert 'space limit' in call_args[0][1].lower()  # Error message
        
        # Verify download was not attempted
        mock_downloader.download_movie.assert_not_called()
    
    def test_download_movie_proceeds_when_space_available(self, temp_dir, mocker):
        """Test that download proceeds when space is available"""
        mock_queue = mocker.MagicMock()
        mock_downloader = mocker.MagicMock()
        mock_downloader.download_movie.return_value = True
        
        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        
        worker = DownloadWorker(
            mock_queue, mock_downloader, str(download_dir),
            max_download_space_gb=100  # Large limit
        )
        
        movie = {
            'title': 'Test Movie',
            'year': 2020,
            'id': 'test123'
        }
        
        # Mock the _is_movie_downloaded to return False
        worker._is_movie_downloaded = mocker.MagicMock(return_value=False)
        
        worker._download_movie(movie)
        
        # Verify download was attempted
        mock_downloader.download_movie.assert_called_once_with(movie)
        
        # Verify movie was added to completed queue
        mock_queue.add_to_completed.assert_called_once_with(movie)
