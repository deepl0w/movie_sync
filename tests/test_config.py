"""Tests for Config"""

import pytest
import json
from pathlib import Path
import os

from config import Config


class TestConfig:
    """Test cases for the Config class"""
    
    def test_load_default_config(self, temp_dir, mocker):
        """Test loading default configuration"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        # Update DEFAULT_CONFIG to use temp_dir
        mocker.patch.object(Config, 'DEFAULT_CONFIG', {
            "username": "",
            "watchlist_file": str(temp_dir / "watchlist.json"),
            "download_queue_file": str(temp_dir / "download_queue.json"),
            "check_interval": 3600,
            "download_directory": os.path.expanduser("~/Downloads")
        })
        
        config = Config.load()
        
        assert config["username"] == ""
        assert config["watchlist_file"] == str(temp_dir / "watchlist.json")
        assert config["download_queue_file"] == str(temp_dir / "download_queue.json")
        assert config["check_interval"] == 3600
        assert "download_directory" in config
    
    def test_load_config_from_file(self, temp_dir, mocker):
        """Test loading configuration from file"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        config_data = {
            "username": "testuser",
            "watchlist_file": "custom_watchlist.json",
            "check_interval": 7200
        }
        
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = Config.load()
        
        assert config["username"] == "testuser"
        assert config["watchlist_file"] == "custom_watchlist.json"
        assert config["check_interval"] == 7200
    
    def test_save_config(self, temp_dir, mocker):
        """Test saving configuration to file"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        config_data = {
            "username": "saveuser",
            "watchlist_file": "saved.json",
            "check_interval": 1800
        }
        
        Config.save(config_data)
        
        # Verify file was created
        config_file = temp_dir / "config.json"
        assert config_file.exists()
        
        # Verify content
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
        
        assert saved_config["username"] == "saveuser"
        assert saved_config["check_interval"] == 1800
    
    def test_load_config_handles_invalid_json(self, temp_dir, mocker, capsys):
        """Test handling of invalid JSON in config file"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        # Create a config file with invalid JSON
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            f.write("invalid json {{{")
        
        config = Config.load()
        
        # Should return defaults on error
        assert config["username"] == ""
        assert "watchlist_file" in config
        
        captured = capsys.readouterr()
        assert "Error loading config" in captured.out
    
    def test_save_config_handles_errors(self, temp_dir, mocker, capsys):
        """Test error handling when saving config fails"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        config_data = {"username": "test"}
        
        # Mock open to raise an exception
        mocker.patch('builtins.open', side_effect=PermissionError("Cannot write"))
        
        Config.save(config_data)
        
        captured = capsys.readouterr()
        assert "Error saving config" in captured.out
    
    def test_config_merge_with_defaults(self, temp_dir, mocker):
        """Test that loaded config merges with defaults"""
        # Mock config directory to use temp_dir
        mocker.patch.object(Config, 'CONFIG_DIR', temp_dir)
        
        # Partial config (missing some fields)
        partial_config = {
            "username": "partialuser"
        }
        
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(partial_config, f)
        
        config = Config.load()
        
        # Should have provided field
        assert config["username"] == "partialuser"
        # Should also have default fields
        assert "watchlist_file" in config
        assert config["check_interval"] == 3600

