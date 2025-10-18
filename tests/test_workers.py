"""Tests for Workers"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from workers import MonitorWorker, DownloadWorker


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
