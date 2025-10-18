"""Tests for CredentialsManager"""

import pytest
import json
from pathlib import Path
from cryptography.fernet import Fernet

from credentials_manager import CredentialsManager


class TestCredentialsManager:
    """Test cases for the CredentialsManager class"""
    
    def test_initialization_creates_config_dir(self, temp_dir):
        """Test that initialization creates config directory"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        assert config_dir.exists()
        assert (config_dir / ".key").exists()
    
    def test_encryption_key_persistence(self, temp_dir):
        """Test that encryption key is reused across instances"""
        config_dir = temp_dir / ".test_config"
        
        # Create first instance
        manager1 = CredentialsManager(str(config_dir))
        key1 = manager1.key
        
        # Create second instance
        manager2 = CredentialsManager(str(config_dir))
        key2 = manager2.key
        
        assert key1 == key2
    
    def test_save_and_get_credentials(self, temp_dir):
        """Test saving and retrieving credentials"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Save credentials
        manager.save_credentials("testservice", "testuser", "testpass123")
        
        # Retrieve credentials
        username, password = manager.get_credentials("testservice")
        
        assert username == "testuser"
        assert password == "testpass123"
    
    def test_get_nonexistent_credentials(self, temp_dir):
        """Test retrieving credentials that don't exist"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        username, password = manager.get_credentials("nonexistent")
        
        assert username is None
        assert password is None
    
    def test_credentials_are_encrypted(self, temp_dir):
        """Test that credentials are actually encrypted on disk"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        manager.save_credentials("testservice", "myuser", "mypassword")
        
        # Read the encrypted file
        creds_file = config_dir / "testservice_credentials.enc"
        with open(creds_file, "rb") as f:
            encrypted_data = f.read()
        
        # Ensure it doesn't contain plaintext password
        assert b"myuser" not in encrypted_data
        assert b"mypassword" not in encrypted_data
    
    def test_clear_credentials(self, temp_dir):
        """Test clearing stored credentials"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Save and verify credentials exist
        manager.save_credentials("testservice", "user", "pass")
        assert manager.credentials_exist("testservice")
        
        # Clear credentials
        manager.clear_credentials("testservice")
        
        # Verify credentials are gone
        assert not manager.credentials_exist("testservice")
        username, password = manager.get_credentials("testservice")
        assert username is None
        assert password is None
    
    def test_credentials_exist(self, temp_dir):
        """Test checking if credentials exist"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Should not exist initially
        assert not manager.credentials_exist("testservice")
        
        # Save credentials
        manager.save_credentials("testservice", "user", "pass")
        
        # Should exist now
        assert manager.credentials_exist("testservice")
    
    def test_list_services(self, temp_dir):
        """Test listing all services with stored credentials"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Initially empty
        assert manager.list_services() == []
        
        # Add multiple services
        manager.save_credentials("service1", "user1", "pass1")
        manager.save_credentials("service2", "user2", "pass2")
        manager.save_credentials("service3", "user3", "pass3")
        
        # Check list
        services = manager.list_services()
        assert len(services) == 3
        assert "service1" in services
        assert "service2" in services
        assert "service3" in services
    
    def test_multiple_services_independent(self, temp_dir):
        """Test that multiple services maintain independent credentials"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Save different credentials for different services
        manager.save_credentials("filelist", "filelistuser", "filelistpass")
        manager.save_credentials("qbittorrent", "qbtuser", "qbtpass")
        
        # Retrieve and verify
        fl_user, fl_pass = manager.get_credentials("filelist")
        qbt_user, qbt_pass = manager.get_credentials("qbittorrent")
        
        assert fl_user == "filelistuser"
        assert fl_pass == "filelistpass"
        assert qbt_user == "qbtuser"
        assert qbt_pass == "qbtpass"
    
    def test_backward_compatibility_filelist(self, temp_dir):
        """Test backward compatibility methods for FileList"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Use old method to save
        manager.save_filelist_credentials("fluser", "flpass")
        
        # Retrieve with both methods
        user1, pass1 = manager.get_filelist_credentials()
        user2, pass2 = manager.get_credentials("filelist")
        
        assert user1 == user2 == "fluser"
        assert pass1 == pass2 == "flpass"
        
        # Test exist and clear
        assert manager.filelist_credentials_exist()
        manager.clear_filelist_credentials()
        assert not manager.filelist_credentials_exist()
    
    def test_backward_compatibility_qbittorrent(self, temp_dir):
        """Test backward compatibility methods for qBittorrent"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Use old method to save
        manager.save_qbittorrent_credentials("qbtuser", "qbtpass")
        
        # Retrieve with both methods
        user1, pass1 = manager.get_qbittorrent_credentials()
        user2, pass2 = manager.get_credentials("qbittorrent")
        
        assert user1 == user2 == "qbtuser"
        assert pass1 == pass2 == "qbtpass"
        
        # Test exist and clear
        assert manager.qbittorrent_credentials_exist()
        manager.clear_qbittorrent_credentials()
        assert not manager.qbittorrent_credentials_exist()
    
    def test_file_permissions(self, temp_dir):
        """Test that credential files have restrictive permissions"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        manager.save_credentials("testservice", "user", "pass")
        
        creds_file = config_dir / "testservice_credentials.enc"
        key_file = config_dir / ".key"
        
        # Check permissions (should be 0o600 = owner read/write only)
        import stat
        creds_mode = creds_file.stat().st_mode & 0o777
        key_mode = key_file.stat().st_mode & 0o777
        
        assert creds_mode == 0o600
        assert key_mode == 0o600
    
    def test_corrupted_credentials_file(self, temp_dir):
        """Test handling of corrupted credential files"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        # Create a corrupted file
        creds_file = config_dir / "corrupted_credentials.enc"
        with open(creds_file, "wb") as f:
            f.write(b"this is not valid encrypted data")
        
        # Should return None without crashing
        username, password = manager.get_credentials("corrupted")
        assert username is None
        assert password is None
    
    def test_special_characters_in_credentials(self, temp_dir):
        """Test that special characters in credentials are handled correctly"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        special_user = "user@example.com"
        special_pass = "p@$$w0rd!#%&*"
        
        manager.save_credentials("testservice", special_user, special_pass)
        username, password = manager.get_credentials("testservice")
        
        assert username == special_user
        assert password == special_pass
    
    def test_empty_credentials(self, temp_dir):
        """Test saving and retrieving empty credentials"""
        config_dir = temp_dir / ".test_config"
        manager = CredentialsManager(str(config_dir))
        
        manager.save_credentials("emptyservice", "", "")
        username, password = manager.get_credentials("emptyservice")
        
        assert username == ""
        assert password == ""
