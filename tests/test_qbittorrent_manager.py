"""Tests for QBittorrentManager"""

import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from qbittorrent_manager import QBittorrentManager


class TestQBittorrentManager:
    """Test cases for the QBittorrentManager class"""
    
    def test_initialization_without_qbittorrentapi(self, mocker, caplog):
        """Test initialization when qbittorrentapi is not available"""
        # Mock the import to fail
        mocker.patch('qbittorrent_manager.qbittorrentapi', None)
        
        manager = QBittorrentManager()
        
        assert manager.client is None
        assert "qbittorrent-api not installed" in caplog.text
    
    def test_initialization_with_credentials(self, mocker):
        """Test initialization with provided credentials"""
        mocker.patch('qbittorrent_manager.qbittorrentapi')
        
        manager = QBittorrentManager(
            host="192.168.1.100",
            port=9090,
            username="admin",
            password="password123",
            use_stored_credentials=False
        )
        
        assert manager.host == "192.168.1.100"
        assert manager.port == 9090
        assert manager.username == "admin"
        assert manager.password == "password123"
    
    def test_get_credentials_from_storage(self, mocker, temp_dir):
        """Test loading credentials from encrypted storage"""
        mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_creds_manager = mocker.patch('qbittorrent_manager.CredentialsManager')
        mock_instance = mock_creds_manager.return_value
        mock_instance.get_qbittorrent_credentials.return_value = ("stored_user", "stored_pass")
        
        manager = QBittorrentManager(use_stored_credentials=True)
        
        assert manager.username == "stored_user"
        assert manager.password == "stored_pass"
    
    def test_get_credentials_prompts_user_when_not_stored(self, mocker, temp_dir):
        """Test that user is prompted for credentials when not stored"""
        mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_creds_manager = mocker.patch('qbittorrent_manager.CredentialsManager')
        mock_instance = mock_creds_manager.return_value
        mock_instance.get_qbittorrent_credentials.return_value = (None, None)
        
        # Mock user input - need more inputs for both username and password prompts
        mocker.patch('builtins.input', side_effect=["inputuser", "inputpass", "inputuser", "inputpass"])
        
        manager = QBittorrentManager(use_stored_credentials=True)
        stored_user, stored_pass = manager._get_credentials()
        
        assert stored_user == "inputuser"
        assert stored_pass == "inputpass"
        mock_instance.save_qbittorrent_credentials.assert_called_with("inputuser", "inputpass")
    
    def test_connect_success(self, mocker, mock_qbt_client):
        """Test successful connection to qBittorrent"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        manager = QBittorrentManager(username="admin", password="pass", use_stored_credentials=False)
        result = manager._connect()
        
        assert result is True
        assert manager.client is not None
        mock_qbt_api.Client.assert_called_with(
            host="localhost",
            port=8080,
            username="admin",
            password="pass"
        )
    
    def test_connect_login_failed(self, mocker, caplog):
        """Test connection failure due to invalid credentials"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        
        # Create a proper exception class
        class MockLoginFailed(Exception):
            pass
        mock_qbt_api.LoginFailed = MockLoginFailed
        
        # Mock the Client class and make version property raise exception
        def create_failing_client(*args, **kwargs):
            client = MagicMock()
            type(client.app).version = property(lambda self: (_ for _ in ()).throw(MockLoginFailed("Invalid")))
            return client
        
        mock_qbt_api.Client = create_failing_client
        
        manager = QBittorrentManager(username="bad", password="bad", use_stored_credentials=False)
        result = manager._connect()
        
        assert result is False
        assert manager.connection_failed is True
        assert "login failed" in caplog.text.lower()
    
    def test_connect_connection_error(self, mocker):
        """Test connection failure when qBittorrent is not running"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        
        # Create proper exception classes
        class MockLoginFailed(Exception):
            pass
        mock_qbt_api.LoginFailed = MockLoginFailed
        
        # Mock the Client class and make version property raise exception
        def create_failing_client(*args, **kwargs):
            client = MagicMock()
            type(client.app).version = property(lambda self: (_ for _ in ()).throw(Exception("Connection refused")))
            return client
        
        mock_qbt_api.Client = create_failing_client
        
        manager = QBittorrentManager(username="admin", password="pass", use_stored_credentials=False)
        result = manager._connect()
        
        assert result is False
    
    def test_ensure_qbittorrent_running_already_running(self, mocker, mock_qbt_client):
        """Test ensure_qbittorrent_running when already running"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        manager = QBittorrentManager(use_stored_credentials=False)
        result = manager._ensure_qbittorrent_running()
        
        assert result is True
    
    def test_ensure_qbittorrent_running_starts_process(self, mocker, mock_qbt_client, caplog):
        """Test starting qBittorrent when not running"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        
        # First connection fails, second succeeds (after starting)
        connection_attempts = [False, False, True]
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._connect = MagicMock(side_effect=connection_attempts)
        
        mock_popen = mocker.patch('subprocess.Popen')
        mock_sleep = mocker.patch('time.sleep')
        
        result = manager._ensure_qbittorrent_running()
        
        assert result is True
        mock_popen.assert_called()
        assert "started qbittorrent" in caplog.text.lower()
    
    def test_ensure_qbittorrent_running_not_found(self, mocker, caplog):
        """Test when qBittorrent executable is not found"""
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._connect = MagicMock(return_value=False)
        
        mocker.patch('subprocess.Popen', side_effect=FileNotFoundError())
        
        result = manager._ensure_qbittorrent_running()
        
        assert result is False
        assert "not found" in caplog.text.lower()
    
    def test_add_torrent_success(self, mocker, mock_qbt_client, temp_dir):
        """Test successfully adding a torrent"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        # Create a fake torrent file
        torrent_file = temp_dir / "test.torrent"
        torrent_file.write_bytes(b"fake torrent content")
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._ensure_qbittorrent_running = MagicMock(return_value=True)
        manager.client = mock_qbt_client  # Set the client directly
        
        result = manager.add_torrent(
            str(torrent_file),
            save_path="/downloads",
            category="TestCategory",
            tags="test,tag"
        )
        
        assert result is True
        mock_qbt_client.torrents_add.assert_called_once()
    
    def test_add_torrent_file_not_found(self, mocker, caplog):
        """Test adding a torrent when file doesn't exist"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._ensure_qbittorrent_running = MagicMock(return_value=True)
        
        result = manager.add_torrent("/nonexistent/file.torrent")
        
        assert result is False
        assert "not found" in caplog.text.lower()
    
    def test_add_torrent_already_exists(self, mocker, mock_qbt_client, temp_dir):
        """Test adding a torrent that already exists"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        # Create a proper exception class
        class MockConflict409Error(Exception):
            pass
        mock_qbt_api.Conflict409Error = MockConflict409Error
        
        mock_qbt_client.torrents_add.side_effect = MockConflict409Error("Torrent already exists")
        
        torrent_file = temp_dir / "test.torrent"
        torrent_file.write_bytes(b"fake torrent content")
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._ensure_qbittorrent_running = MagicMock(return_value=True)
        manager.client = mock_qbt_client  # Set the client directly
        
        result = manager.add_torrent(str(torrent_file))
        
        # Should still return True (already exists is OK)
        assert result is True
    
    def test_add_torrent_creates_category(self, mocker, mock_qbt_client, temp_dir):
        """Test that adding a torrent creates category if needed"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        mock_qbt_client.torrents_categories.return_value = {"ExistingCat": {}}
        
        torrent_file = temp_dir / "test.torrent"
        torrent_file.write_bytes(b"fake torrent content")
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager._ensure_qbittorrent_running = MagicMock(return_value=True)
        manager.client = mock_qbt_client  # Set the client directly
        
        manager.add_torrent(str(torrent_file), category="NewCategory")
        
        mock_qbt_client.torrents_create_category.assert_called_once_with("NewCategory")
    
    def test_add_torrent_qbittorrent_not_available(self, mocker, caplog):
        """Test adding torrent when qBittorrent API is not available"""
        mocker.patch('qbittorrent_manager.qbittorrentapi', None)
        
        manager = QBittorrentManager()
        result = manager.add_torrent("/path/to/file.torrent")
        
        assert result is False
        assert "not available" in caplog.text.lower()
    
    def test_get_torrent_info_success(self, mocker, mock_qbt_client):
        """Test getting torrent information"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        # Mock torrent info
        mock_torrent = MagicMock()
        mock_torrent.name = "Test Movie"
        mock_torrent.progress = 0.75
        mock_torrent.state = "downloading"
        mock_torrent.downloaded = 1024 * 1024 * 500  # 500 MB
        mock_torrent.size = 1024 * 1024 * 1000  # 1000 MB
        mock_torrent.eta = 300  # 5 minutes
        mock_torrent.num_seeds = 10
        
        mock_qbt_client.torrents_info.return_value = [mock_torrent]
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager.client = mock_qbt_client
        
        info = manager.get_torrent_info("abc123")
        
        assert info is not None
        assert info["name"] == "Test Movie"
        assert info["progress"] == 0.75
        assert info["state"] == "downloading"
        assert info["num_seeds"] == 10
    
    def test_get_torrent_info_not_found(self, mocker, mock_qbt_client):
        """Test getting info for non-existent torrent"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        mock_qbt_client.torrents_info.return_value = []
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager.client = mock_qbt_client
        
        info = manager.get_torrent_info("nonexistent")
        
        assert info is None
    
    def test_list_torrents_success(self, mocker, mock_qbt_client):
        """Test listing all torrents"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        # Mock multiple torrents
        mock_torrent1 = MagicMock()
        mock_torrent1.name = "Movie 1"
        mock_torrent1.progress = 1.0
        mock_torrent1.state = "seeding"
        mock_torrent1.category = "Movies"
        mock_torrent1.size = 1024 * 1024 * 1000
        mock_torrent1.eta = 0
        
        mock_torrent2 = MagicMock()
        mock_torrent2.name = "Movie 2"
        mock_torrent2.progress = 0.5
        mock_torrent2.state = "downloading"
        mock_torrent2.category = "Movies"
        mock_torrent2.size = 1024 * 1024 * 2000
        mock_torrent2.eta = 600
        
        mock_qbt_client.torrents_info.return_value = [mock_torrent1, mock_torrent2]
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager.client = mock_qbt_client
        
        torrents = manager.list_torrents()
        
        assert len(torrents) == 2
        assert torrents[0]["name"] == "Movie 1"
        assert torrents[0]["progress"] == 100.0
        assert torrents[1]["name"] == "Movie 2"
        assert torrents[1]["progress"] == 50.0
    
    def test_list_torrents_filtered_by_category(self, mocker, mock_qbt_client):
        """Test listing torrents filtered by category"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager.client = mock_qbt_client
        
        manager.list_torrents(category="Movies")
        
        mock_qbt_client.torrents_info.assert_called_once_with(category="Movies")
    
    def test_list_torrents_connection_error(self, mocker, mock_qbt_client, caplog):
        """Test listing torrents when connection fails"""
        mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
        mock_qbt_api.Client.return_value = mock_qbt_client
        mock_qbt_client.torrents_info.side_effect = Exception("Connection error")
        
        manager = QBittorrentManager(use_stored_credentials=False)
        manager.client = mock_qbt_client
        
        torrents = manager.list_torrents()
        
        assert torrents == []
        assert "failed to list torrents" in caplog.text.lower()
