"""Tests for FileListDownloader"""

import pytest
import json
import responses
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from filelist_downloader import FileListDownloader


class TestFileListDownloader:
    """Test cases for the FileListDownloader class"""
    
    def test_initialization_default_config(self, temp_dir, mocker):
        """Test initialization with default configuration"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            torrent_dir=str(temp_dir / "torrents"),
            use_qbittorrent=False
        )
        
        assert downloader.torrent_dir == temp_dir / "torrents"
        assert downloader.prefer_freeleech is True
        assert downloader.minimum_seeders == 1
    
    def test_load_config_from_file(self, temp_dir, json_file_helper, sample_filelist_config, mocker):
        """Test loading configuration from JSON file"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        config_file = json_file_helper("filelist_config.json", sample_filelist_config)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            config_file=str(config_file),
            use_qbittorrent=False
        )
        
        assert len(downloader.movie_categories) == 4
        assert downloader.category_priority[6] == 1  # 4K has priority 1
        assert downloader.category_priority[4] == 2  # HD has priority 2
        assert downloader.prefer_freeleech is True
    
    def test_load_config_missing_file(self, temp_dir, mocker, capsys):
        """Test handling of missing config file"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            config_file=str(temp_dir / "nonexistent.json"),
            use_qbittorrent=False
        )
        
        # Should use defaults
        assert len(downloader.movie_categories) == 4
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()
    
    def test_get_credentials_from_storage(self, temp_dir, mocker):
        """Test getting credentials from storage"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("testuser", "testpass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        result = downloader._get_credentials()
        
        assert result is True
        assert downloader.username == "testuser"
        assert downloader.passkey == "testpass"
    
    def test_get_credentials_prompts_user(self, temp_dir, mocker):
        """Test prompting user for credentials when not stored"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = (None, None)
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        mocker.patch('builtins.input', side_effect=["newuser", "newpass"])
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        result = downloader._get_credentials()
        
        assert result is True
        assert downloader.username == "newuser"
        assert downloader.passkey == "newpass"
        mock_instance.save_filelist_credentials.assert_called_once_with("newuser", "newpass")
    
    @responses.activate
    def test_search_movie_by_imdb(self, temp_dir, sample_movie, sample_torrent_result, mocker):
        """Test searching for a movie by IMDB ID"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock API response
        api_response = [sample_torrent_result]
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json=api_response,
            status=200
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        results = downloader._search_movie(sample_movie)
        
        assert len(results) == 1
        assert results[0]["name"] == sample_torrent_result["name"]
        assert results[0]["seeders"] == 42
    
    @responses.activate
    def test_search_movie_by_title(self, temp_dir, sample_torrent_result, mocker):
        """Test searching for a movie by title (no IMDB)"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        movie = {"title": "The Matrix (1999)"}
        
        # Mock API response
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json=[sample_torrent_result],
            status=200
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        results = downloader._search_movie(movie)
        
        # Verify correct search parameters
        assert len(responses.calls) == 1
        params = responses.calls[0].request.params
        assert params["type"] == "name"
        assert "Matrix" in params["query"]
    
    @responses.activate
    def test_search_movie_rate_limit_error(self, temp_dir, mocker, capsys):
        """Test handling of rate limit error (429)"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock rate limit error
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json={"error": 429, "message": "Rate limit exceeded"},
            status=200
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        results = downloader._search_movie({"title": "Test Movie"})
        
        assert results == []
        captured = capsys.readouterr()
        assert "Rate limit" in captured.out
    
    @responses.activate
    def test_search_movie_invalid_credentials(self, temp_dir, mocker, capsys):
        """Test handling of invalid credentials error (403)"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("bad", "bad")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock invalid credentials error
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json={"error": 403, "message": "Invalid credentials"},
            status=200
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        results = downloader._search_movie({"title": "Test Movie"})
        
        assert results == []
        # Credentials should be cleared
        mock_instance.clear_filelist_credentials.assert_called_once()
    
    def test_select_best_torrent_by_quality(self, temp_dir, mocker):
        """Test selecting best torrent prioritizes quality"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        # Multiple torrents with different qualities
        torrents = [
            {"name": "SD", "category": 1, "seeders": 100, "freeleech": 0},  # SD, priority 4
            {"name": "HD", "category": 4, "seeders": 50, "freeleech": 0},   # HD, priority 2
            {"name": "4K", "category": 6, "seeders": 10, "freeleech": 0},   # 4K, priority 1
        ]
        
        best = downloader._select_best_torrent(torrents)
        
        # Should select 4K even with fewer seeders
        assert best["name"] == "4K"
        assert best["category"] == 6
    
    def test_select_best_torrent_prefers_freeleech(self, temp_dir, mocker):
        """Test selecting best torrent prefers freeleech within same quality"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        downloader.prefer_freeleech = True
        
        # Multiple torrents same quality, different freeleech
        torrents = [
            {"name": "Normal", "category": 4, "seeders": 100, "freeleech": 0},
            {"name": "Freeleech", "category": 4, "seeders": 50, "freeleech": 1},
        ]
        
        best = downloader._select_best_torrent(torrents)
        
        # Should select freeleech even with fewer seeders
        assert best["name"] == "Freeleech"
    
    def test_select_best_torrent_by_seeders(self, temp_dir, mocker):
        """Test selecting best torrent by seeders when same quality and freeleech"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        torrents = [
            {"name": "Low Seeds", "category": 4, "seeders": 10, "freeleech": 0},
            {"name": "High Seeds", "category": 4, "seeders": 100, "freeleech": 0},
        ]
        
        best = downloader._select_best_torrent(torrents)
        
        assert best["name"] == "High Seeds"
        assert best["seeders"] == 100
    
    def test_select_best_torrent_minimum_seeders(self, temp_dir, mocker):
        """Test filtering by minimum seeders"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        downloader.minimum_seeders = 10
        
        torrents = [
            {"name": "Low Seeds", "category": 4, "seeders": 5, "freeleech": 0},
            {"name": "High Seeds", "category": 4, "seeders": 50, "freeleech": 0},
        ]
        
        best = downloader._select_best_torrent(torrents)
        
        # Should only consider torrents with >= 10 seeders
        assert best["name"] == "High Seeds"
    
    def test_select_best_torrent_empty_list(self, temp_dir, mocker):
        """Test selecting from empty torrent list"""
        mocker.patch('filelist_downloader.CredentialsManager')
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        best = downloader._select_best_torrent([])
        
        assert best is None
    
    @responses.activate
    def test_download_torrent_file_success(self, temp_dir, mocker):
        """Test successfully downloading a torrent file"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock torrent file download
        torrent_content = b"d8:announce44:https://tracker.example.com/announce10:created"
        responses.add(
            responses.GET,
            "https://filelist.io/download.php",
            body=torrent_content,
            status=200,
            headers={"Content-Type": "application/x-bittorrent"}
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            torrent_dir=str(temp_dir / "torrents"),
            use_qbittorrent=False
        )
        
        result = downloader._download_torrent_file("12345", "Test Movie")
        
        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_bytes() == torrent_content
    
    @responses.activate
    def test_download_torrent_file_invalid_response(self, temp_dir, mocker, capsys):
        """Test handling invalid torrent file response"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock invalid response (HTML instead of torrent)
        responses.add(
            responses.GET,
            "https://filelist.io/download.php",
            body=b"<html>Error</html>",
            status=200,
            headers={"Content-Type": "text/html"}
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            torrent_dir=str(temp_dir / "torrents"),
            use_qbittorrent=False
        )
        
        result = downloader._download_torrent_file("12345", "Test Movie")
        
        assert result is None
        captured = capsys.readouterr()
        assert "not a torrent file" in captured.out.lower()
    
    @responses.activate
    def test_download_movie_full_workflow(self, temp_dir, sample_movie, sample_torrent_result, mocker):
        """Test complete movie download workflow"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock search results
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json=[sample_torrent_result],
            status=200
        )
        
        # Mock torrent download
        torrent_content = b"d8:announce44:https://tracker.example.com/announce10:created"
        responses.add(
            responses.GET,
            "https://filelist.io/download.php",
            body=torrent_content,
            status=200,
            headers={"Content-Type": "application/x-bittorrent"}
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            torrent_dir=str(temp_dir / "torrents"),
            use_qbittorrent=False
        )
        
        result = downloader.download_movie(sample_movie)
        
        assert result is True
        # Verify torrent file was created
        assert len(list((temp_dir / "torrents").glob("*.torrent"))) == 1
    
    @responses.activate
    def test_download_movie_with_qbittorrent(self, temp_dir, sample_movie, sample_torrent_result, mocker):
        """Test movie download with qBittorrent integration"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        
        # Mock qBittorrent manager
        mock_qbt = mocker.MagicMock()
        mock_qbt.add_torrent.return_value = True
        mock_qbt_class = mocker.patch('filelist_downloader.QBittorrentManager', return_value=mock_qbt)
        
        # Mock API responses
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json=[sample_torrent_result],
            status=200
        )
        
        torrent_content = b"d8:announce44:https://tracker.example.com/announce"
        responses.add(
            responses.GET,
            "https://filelist.io/download.php",
            body=torrent_content,
            status=200,
            headers={"Content-Type": "application/x-bittorrent"}
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            torrent_dir=str(temp_dir / "torrents"),
            use_qbittorrent=True
        )
        downloader.qbt_manager = mock_qbt
        downloader.use_qbittorrent = True
        
        result = downloader.download_movie(sample_movie)
        
        assert result is True
        # Verify qBittorrent was called
        mock_qbt.add_torrent.assert_called_once()
    
    @responses.activate
    def test_download_movie_no_results(self, temp_dir, sample_movie, mocker, capsys):
        """Test downloading movie when no search results found"""
        mock_creds = mocker.patch('filelist_downloader.CredentialsManager')
        mock_instance = mock_creds.return_value
        mock_instance.get_filelist_credentials.return_value = ("user", "pass")
        mocker.patch('filelist_downloader.QBittorrentManager', return_value=None)
        
        # Mock empty search results
        responses.add(
            responses.GET,
            "https://filelist.io/api.php",
            json=[],
            status=200
        )
        
        downloader = FileListDownloader(
            queue_file=str(temp_dir / "queue.json"),
            use_qbittorrent=False
        )
        
        result = downloader.download_movie(sample_movie)
        
        assert result is False
        captured = capsys.readouterr()
        assert "No torrents found" in captured.out
