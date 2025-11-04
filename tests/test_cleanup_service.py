"""Tests for cleanup_service.py"""

import pytest
from pathlib import Path
import json
from unittest.mock import MagicMock, patch
from cleanup_service import CleanupService


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing"""
    download_dir = tmp_path / "downloads"
    torrent_dir = tmp_path / "torrents"
    download_dir.mkdir()
    torrent_dir.mkdir()
    return download_dir, torrent_dir


@pytest.fixture
def mock_qbt_manager():
    """Create a mock qBittorrent manager"""
    manager = MagicMock()
    manager.client = MagicMock()
    return manager


@pytest.fixture
def cleanup_service(temp_dirs):
    """Create cleanup service with temp directories"""
    download_dir, torrent_dir = temp_dirs
    return CleanupService(str(download_dir), str(torrent_dir))


@pytest.fixture
def cleanup_service_with_qbt(temp_dirs, mock_qbt_manager):
    """Create cleanup service with qBittorrent manager"""
    download_dir, torrent_dir = temp_dirs
    return CleanupService(str(download_dir), str(torrent_dir), mock_qbt_manager)


class TestCleanupServiceInit:
    """Test cleanup service initialization"""
    
    def test_init_without_qbt(self, temp_dirs):
        """Test initialization without qBittorrent manager"""
        download_dir, torrent_dir = temp_dirs
        service = CleanupService(str(download_dir), str(torrent_dir))
        
        assert service.download_dir == download_dir
        assert service.torrent_dir == torrent_dir
        assert service.qbt_manager is None
    
    def test_init_with_qbt(self, temp_dirs, mock_qbt_manager):
        """Test initialization with qBittorrent manager"""
        download_dir, torrent_dir = temp_dirs
        service = CleanupService(str(download_dir), str(torrent_dir), mock_qbt_manager)
        
        assert service.download_dir == download_dir
        assert service.torrent_dir == torrent_dir
        assert service.qbt_manager is mock_qbt_manager


class TestCleanupMovie:
    """Test cleanup_movie method"""
    
    def test_cleanup_movie_no_title(self, cleanup_service):
        """Test cleanup with no title provided"""
        movie = {'year': 2020}
        results = cleanup_service.cleanup_movie(movie)
        
        assert results['files_deleted'] is False
        assert results['torrent_deleted'] is False
        assert results['qbt_removed'] is False
        assert len(results['errors']) == 1
        assert 'No title provided' in results['errors'][0]
    
    def test_cleanup_movie_files_only(self, cleanup_service, temp_dirs):
        """Test cleanup with only file deletion"""
        download_dir, _ = temp_dirs
        
        # Create a movie file
        movie_file = download_dir / "Inception.2010.1080p.BluRay.mkv"
        movie_file.write_text("fake movie content")
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service.cleanup_movie(
            movie, 
            delete_files=True, 
            delete_torrent=False, 
            remove_from_qbt=False
        )
        
        assert results['files_deleted'] is True
        assert results['torrent_deleted'] is False
        assert results['qbt_removed'] is False
        assert not movie_file.exists()
    
    def test_cleanup_movie_torrent_only(self, cleanup_service, temp_dirs):
        """Test cleanup with only torrent deletion"""
        _, torrent_dir = temp_dirs
        
        # Create a torrent file
        torrent_file = torrent_dir / "Inception.2010.1080p.BluRay.torrent"
        torrent_file.write_text("fake torrent content")
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service.cleanup_movie(
            movie,
            delete_files=False,
            delete_torrent=True,
            remove_from_qbt=False
        )
        
        assert results['files_deleted'] is False
        assert results['torrent_deleted'] is True
        assert results['qbt_removed'] is False
        assert not torrent_file.exists()
    
    def test_cleanup_movie_qbt_only(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test cleanup with only qBittorrent removal"""
        # Mock torrent exists
        mock_torrent = MagicMock()
        mock_torrent.name = "Inception.2010.1080p.BluRay"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service_with_qbt.cleanup_movie(
            movie,
            delete_files=False,
            delete_torrent=False,
            remove_from_qbt=True
        )
        
        assert results['files_deleted'] is False
        assert results['torrent_deleted'] is False
        assert results['qbt_removed'] is True
        mock_qbt_manager.client.torrents_delete.assert_called_once()
    
    def test_cleanup_movie_all_methods(self, cleanup_service_with_qbt, temp_dirs, mock_qbt_manager):
        """Test cleanup with all methods enabled"""
        download_dir, torrent_dir = temp_dirs
        
        # Create files
        movie_file = download_dir / "Inception.2010.1080p.BluRay.mkv"
        movie_file.write_text("fake movie")
        torrent_file = torrent_dir / "Inception.2010.1080p.BluRay.torrent"
        torrent_file.write_text("fake torrent")
        
        # Mock qBittorrent
        mock_torrent = MagicMock()
        mock_torrent.name = "Inception.2010.1080p.BluRay"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service_with_qbt.cleanup_movie(
            movie,
            delete_files=True,
            delete_torrent=True,
            remove_from_qbt=True
        )
        
        assert results['files_deleted'] is True
        assert results['torrent_deleted'] is True
        assert results['qbt_removed'] is True
        assert len(results['errors']) == 0
        assert not movie_file.exists()
        assert not torrent_file.exists()
    
    def test_cleanup_movie_file_error(self, cleanup_service, temp_dirs, mocker):
        """Test cleanup with file deletion error"""
        # Mock _delete_movie_files to raise exception
        mocker.patch.object(
            cleanup_service, 
            '_delete_movie_files', 
            side_effect=Exception("Permission denied")
        )
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service.cleanup_movie(movie, delete_files=True)
        
        assert results['files_deleted'] is False
        assert len(results['errors']) > 0
        assert 'Permission denied' in results['errors'][0]
    
    def test_cleanup_movie_torrent_error(self, cleanup_service, temp_dirs, mocker):
        """Test cleanup with torrent deletion error"""
        mocker.patch.object(
            cleanup_service,
            '_delete_torrent_file',
            side_effect=Exception("File locked")
        )
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service.cleanup_movie(movie, delete_torrent=True)
        
        assert results['torrent_deleted'] is False
        assert len(results['errors']) > 0
        assert 'File locked' in results['errors'][0]
    
    def test_cleanup_movie_qbt_error(self, cleanup_service_with_qbt, mock_qbt_manager, mocker):
        """Test cleanup with qBittorrent error"""
        mocker.patch.object(
            cleanup_service_with_qbt,
            '_remove_from_qbittorrent',
            side_effect=Exception("Connection lost")
        )
        
        movie = {'title': 'Inception', 'year': '2010'}
        results = cleanup_service_with_qbt.cleanup_movie(movie, remove_from_qbt=True)
        
        assert results['qbt_removed'] is False
        assert len(results['errors']) > 0
        assert 'Connection lost' in results['errors'][0]
    
    def test_cleanup_movie_qbt_client_none(self, temp_dirs):
        """Test cleanup when qBittorrent client is None"""
        download_dir, torrent_dir = temp_dirs
        qbt_manager = MagicMock()
        qbt_manager.client = None
        
        service = CleanupService(str(download_dir), str(torrent_dir), qbt_manager)
        movie = {'title': 'Inception', 'year': '2010'}
        
        results = service.cleanup_movie(movie, remove_from_qbt=True)
        
        # Should not attempt qBittorrent removal when client is None
        assert results['qbt_removed'] is False


class TestDeleteMovieFiles:
    """Test _delete_movie_files method"""
    
    def test_delete_exact_match(self, cleanup_service, temp_dirs):
        """Test deleting file with exact title match"""
        download_dir, _ = temp_dirs
        
        movie_file = download_dir / "Inception.2010.1080p.BluRay.mkv"
        movie_file.write_text("content")
        
        result = cleanup_service._delete_movie_files("Inception", "2010")
        
        assert result is True
        assert not movie_file.exists()
    
    def test_delete_fuzzy_match(self, cleanup_service, temp_dirs):
        """Test deleting file with fuzzy title match"""
        download_dir, _ = temp_dirs
        
        movie_file = download_dir / "The.Inception.Movie.2010.1080p.mkv"
        movie_file.write_text("content")
        
        result = cleanup_service._delete_movie_files("Inception", "2010")
        
        assert result is True
        assert not movie_file.exists()
    
    def test_delete_directory(self, cleanup_service, temp_dirs):
        """Test deleting movie directory"""
        download_dir, _ = temp_dirs
        
        movie_dir = download_dir / "Inception.2010.1080p.BluRay"
        movie_dir.mkdir()
        (movie_dir / "movie.mkv").write_text("content")
        (movie_dir / "subtitle.srt").write_text("subs")
        
        result = cleanup_service._delete_movie_files("Inception", "2010")
        
        assert result is True
        assert not movie_dir.exists()
    
    def test_delete_no_match(self, cleanup_service, temp_dirs):
        """Test when no matching files found"""
        download_dir, _ = temp_dirs
        
        # Create unrelated file
        other_file = download_dir / "OtherMovie.2020.mkv"
        other_file.write_text("content")
        
        result = cleanup_service._delete_movie_files("Inception", "2010")
        
        assert result is False
        assert other_file.exists()
    
    def test_delete_year_mismatch(self, cleanup_service, temp_dirs):
        """Test that year must match"""
        download_dir, _ = temp_dirs
        
        # Same title, wrong year
        movie_file = download_dir / "Inception.2020.1080p.BluRay.mkv"
        movie_file.write_text("content")
        
        result = cleanup_service._delete_movie_files("Inception", "2010")
        
        assert result is False
        assert movie_file.exists()


class TestDeleteTorrentFile:
    """Test _delete_torrent_file method"""
    
    def test_delete_torrent_exact_match(self, cleanup_service, temp_dirs):
        """Test deleting torrent with exact match"""
        _, torrent_dir = temp_dirs
        
        torrent_file = torrent_dir / "Inception.2010.1080p.BluRay.torrent"
        torrent_file.write_text("torrent data")
        
        result = cleanup_service._delete_torrent_file("Inception", "2010")
        
        assert result is True
        assert not torrent_file.exists()
    
    def test_delete_torrent_fuzzy_match(self, cleanup_service, temp_dirs):
        """Test deleting torrent with fuzzy match"""
        _, torrent_dir = temp_dirs
        
        torrent_file = torrent_dir / "The.Inception.2010.REMUX.torrent"
        torrent_file.write_text("torrent data")
        
        result = cleanup_service._delete_torrent_file("Inception", "2010")
        
        assert result is True
        assert not torrent_file.exists()
    
    def test_delete_torrent_no_match(self, cleanup_service, temp_dirs):
        """Test when no matching torrent found"""
        _, torrent_dir = temp_dirs
        
        other_file = torrent_dir / "OtherMovie.2020.torrent"
        other_file.write_text("torrent data")
        
        result = cleanup_service._delete_torrent_file("Inception", "2010")
        
        assert result is False
        assert other_file.exists()
    
    def test_delete_torrent_year_mismatch(self, cleanup_service, temp_dirs):
        """Test that torrent year must match"""
        _, torrent_dir = temp_dirs
        
        torrent_file = torrent_dir / "Inception.2020.torrent"
        torrent_file.write_text("torrent data")
        
        result = cleanup_service._delete_torrent_file("Inception", "2010")
        
        assert result is False
        assert torrent_file.exists()


class TestRemoveFromQBittorrent:
    """Test _remove_from_qbittorrent method"""
    
    def test_remove_exact_match(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test removing torrent with exact name match"""
        mock_torrent = MagicMock()
        mock_torrent.name = "Inception.2010.1080p.BluRay"
        mock_torrent.hash = "abc123"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        result = cleanup_service_with_qbt._remove_from_qbittorrent("Inception", "2010")
        
        assert result is True
        mock_qbt_manager.client.torrents_delete.assert_called_once_with(
            delete_files=True, 
            torrent_hashes="abc123"
        )
    
    def test_remove_fuzzy_match(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test removing torrent with fuzzy name match"""
        mock_torrent = MagicMock()
        mock_torrent.name = "The Inception Movie (2010) [1080p]"
        mock_torrent.hash = "def456"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        result = cleanup_service_with_qbt._remove_from_qbittorrent("Inception", "2010")
        
        assert result is True
        mock_qbt_manager.client.torrents_delete.assert_called_once()
    
    def test_remove_no_match(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test when no matching torrent found"""
        mock_torrent = MagicMock()
        mock_torrent.name = "OtherMovie.2020.1080p"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        result = cleanup_service_with_qbt._remove_from_qbittorrent("Inception", "2010")
        
        assert result is False
        mock_qbt_manager.client.torrents_delete.assert_not_called()
    
    def test_remove_year_mismatch(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test that torrent year must match"""
        mock_torrent = MagicMock()
        mock_torrent.name = "Inception.2020.1080p.BluRay"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        result = cleanup_service_with_qbt._remove_from_qbittorrent("Inception", "2010")
        
        assert result is False
        mock_qbt_manager.client.torrents_delete.assert_not_called()
    
    def test_remove_multiple_torrents_best_match(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test removing all matching torrents when multiple exist"""
        torrent1 = MagicMock()
        torrent1.name = "Inception.2010.1080p.BluRay"  # Match
        torrent1.hash = "hash1"
        
        torrent2 = MagicMock()
        torrent2.name = "Inception.Movie.2010.720p"  # Match
        torrent2.hash = "hash2"
        
        mock_qbt_manager.client.torrents_info.return_value = [torrent1, torrent2]
        
        result = cleanup_service_with_qbt._remove_from_qbittorrent("Inception", "2010")
        
        assert result is True
        # Should delete ALL torrents that match
        assert mock_qbt_manager.client.torrents_delete.call_count == 2


class TestNormalizeTitle:
    """Test _normalize_title helper method"""
    
    def test_normalize_basic(self, cleanup_service):
        """Test basic title normalization"""
        result = cleanup_service._normalize_title("The Inception Movie")
        assert result == "the.inception.movie"
    
    def test_normalize_special_chars(self, cleanup_service):
        """Test normalization with special characters and year stripping"""
        result = cleanup_service._normalize_title("The Matrix: Reloaded (2003)")
        # Colons and apostrophes removed, spaces to dots, year in parentheses stripped
        assert result == "the.matrix.reloaded"
    
    def test_normalize_dots_already(self, cleanup_service):
        """Test normalization with dots already present"""
        result = cleanup_service._normalize_title("The.Dark.Knight.2008")
        assert result == "the.dark.knight.2008"
    
    def test_normalize_lowercase(self, cleanup_service):
        """Test normalization converts to lowercase"""
        result = cleanup_service._normalize_title("INCEPTION")
        assert result == "inception"
    
    def test_normalize_empty_string(self, cleanup_service):
        """Test normalization with empty string"""
        result = cleanup_service._normalize_title("")
        assert result == ""
    
    def test_normalize_apostrophe_removed(self, cleanup_service):
        """Test that apostrophes are removed"""
        result = cleanup_service._normalize_title("Ocean's Eleven")
        assert result == "oceans.eleven"
    
    def test_normalize_year_in_parentheses(self, cleanup_service):
        """Test that year in parentheses is stripped (regression test for Amadeus bug)"""
        result = cleanup_service._normalize_title("Amadeus (1984)")
        assert result == "amadeus"
    
    def test_normalize_year_in_parentheses_with_spaces(self, cleanup_service):
        """Test year stripping with various spacing"""
        result = cleanup_service._normalize_title("The Godfather ( 1972 )")
        assert result == "the.godfather"


class TestExtractTitlePart:
    """Test _extract_title_part method"""
    
    def test_extract_before_quality(self, cleanup_service):
        """Test extracting title before quality indicator"""
        result = cleanup_service._extract_title_part("Inception.2010.1080p.BluRay.x264")
        assert "1080p" not in result
        assert "BluRay" not in result.lower() or "bluray" not in result.lower()
    
    def test_extract_with_multiple_indicators(self, cleanup_service):
        """Test extraction with multiple quality indicators"""
        result = cleanup_service._extract_title_part("Movie.Name.2020.HDTV.x264.AAC")
        # Should split at first quality indicator
        assert "HDTV" not in result or result.endswith("HDTV")


class TestGetCleanupPreview:
    """Test get_cleanup_preview method"""
    
    def test_preview_no_title(self, cleanup_service):
        """Test preview with no title"""
        movie = {'year': 2020}
        preview = cleanup_service.get_cleanup_preview(movie)
        
        assert preview['files'] == []
        assert preview['torrents'] == []
        assert preview['qbt_torrents'] == []
    
    def test_preview_with_files(self, cleanup_service, temp_dirs):
        """Test preview finds matching files"""
        download_dir, _ = temp_dirs
        
        movie_file = download_dir / "Inception.2010.1080p.mkv"
        movie_file.write_text("content")
        
        movie = {'title': 'Inception', 'year': '2010'}
        preview = cleanup_service.get_cleanup_preview(movie)
        
        assert len(preview['files']) > 0
        assert any('Inception' in f for f in preview['files'])
    
    def test_preview_with_torrents(self, cleanup_service, temp_dirs):
        """Test preview finds matching torrents"""
        _, torrent_dir = temp_dirs
        
        torrent_file = torrent_dir / "Inception.2010.1080p.torrent"
        torrent_file.write_text("content")
        
        movie = {'title': 'Inception', 'year': '2010'}
        preview = cleanup_service.get_cleanup_preview(movie)
        
        assert len(preview['torrents']) > 0
        assert any('Inception' in t for t in preview['torrents'])
    
    def test_preview_with_qbt(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test preview finds qBittorrent torrents"""
        mock_torrent = MagicMock()
        mock_torrent.name = "Inception.2010.1080p.BluRay"
        mock_qbt_manager.client.torrents_info.return_value = [mock_torrent]
        
        movie = {'title': 'Inception', 'year': '2010'}
        preview = cleanup_service_with_qbt.get_cleanup_preview(movie)
        
        assert len(preview['qbt_torrents']) > 0
        assert "Inception" in preview['qbt_torrents'][0]
    
    def test_preview_qbt_error(self, cleanup_service_with_qbt, mock_qbt_manager):
        """Test preview handles qBittorrent errors gracefully"""
        mock_qbt_manager.client.torrents_info.side_effect = Exception("Connection lost")
        
        movie = {'title': 'Inception', 'year': '2010'}
        preview = cleanup_service_with_qbt.get_cleanup_preview(movie)
        
        # Should not crash, just return empty qbt_torrents
        assert preview['qbt_torrents'] == []


class TestSafeDelete:
    """Test _safe_delete method"""
    
    def test_safe_delete_file(self, cleanup_service, temp_dirs):
        """Test safely deleting a file"""
        download_dir, _ = temp_dirs
        test_file = download_dir / "test.txt"
        test_file.write_text("content")
        
        cleanup_service._safe_delete(test_file)
        
        assert not test_file.exists()
    
    def test_safe_delete_directory(self, cleanup_service, temp_dirs):
        """Test safely deleting a directory"""
        download_dir, _ = temp_dirs
        test_dir = download_dir / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        cleanup_service._safe_delete(test_dir)
        
        assert not test_dir.exists()
    
    def test_safe_delete_nonexistent(self, cleanup_service, temp_dirs):
        """Test safely deleting nonexistent path (should not crash)"""
        download_dir, _ = temp_dirs
        fake_path = download_dir / "nonexistent.txt"
        
        # Should not raise exception
        cleanup_service._safe_delete(fake_path)
