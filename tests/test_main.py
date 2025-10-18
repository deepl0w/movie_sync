"""Integration tests for main.py"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import argparse

from main import main, setup_configuration, run_movie_sync


class TestMain:
    """Test cases for main entry point"""
    
    def test_main_no_username_error(self, temp_dir, capsys):
        """Test that main() errors when username is not configured"""
        with patch('main.Config.load') as mock_load:
            mock_load.return_value = {"check_interval": 3600}  # No username
            
            with patch('sys.argv', ['main.py']):
                result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "username is required" in captured.out.lower()
    
    def test_main_config_mode(self, temp_dir, monkeypatch):
        """Test main() in config mode"""
        with patch('main.Config.load') as mock_load, \
             patch('main.Config.save') as mock_save:
            
            mock_load.return_value = {
                "username": "testuser",
                "check_interval": 3600,
                "download_directory": "~/Downloads",
                "retry_interval": 3600,
                "max_retries": 5
            }
            
            # Simulate user pressing enter for all prompts (keep defaults)
            inputs = iter(['', '', '', '', ''])
            monkeypatch.setattr('builtins.input', lambda x: next(inputs))
            
            with patch('sys.argv', ['main.py', '--config']):
                result = main()
            
            assert result == 0
            assert mock_save.called
    
    def test_main_stats_mode_empty(self, temp_dir, capsys):
        """Test main() in stats mode with empty queues"""
        with patch('main.Config.load') as mock_load, \
             patch('main.QueueManager') as mock_qm_class:
            
            mock_load.return_value = {
                "username": "testuser",
                "max_retries": 5
            }
            
            mock_qm = MagicMock()
            mock_qm.get_statistics.return_value = {
                "pending": 0,
                "failed": 0,
                "completed": 0,
                "permanent_failures": 0
            }
            mock_qm.get_movies_ready_for_retry.return_value = []
            mock_qm.get_permanent_failures.return_value = []
            mock_qm_class.return_value = mock_qm
            
            with patch('sys.argv', ['main.py', '--stats']):
                result = main()
            
            assert result == 0
            captured = capsys.readouterr()
            assert "Pending:    0" in captured.out
            assert "Failed:     0" in captured.out
            assert "Completed:  0" in captured.out
    
    def test_main_stats_mode_with_failures(self, temp_dir, capsys):
        """Test main() stats mode showing failed movies"""
        with patch('main.Config.load') as mock_load, \
             patch('main.QueueManager') as mock_qm_class:
            
            mock_load.return_value = {
                "username": "testuser",
                "max_retries": 5
            }
            
            mock_qm = MagicMock()
            mock_qm.get_statistics.return_value = {
                "pending": 2,
                "failed": 3,
                "completed": 10,
                "permanent_failures": 1
            }
            mock_qm.get_movies_ready_for_retry.return_value = [
                {"title": "Movie 1", "retry_count": 2},
                {"title": "Movie 2", "retry_count": 1}
            ]
            mock_qm.get_permanent_failures.return_value = [
                {"title": "Failed Movie", "last_error": "Not found"}
            ]
            mock_qm_class.return_value = mock_qm
            
            with patch('sys.argv', ['main.py', '--stats']):
                result = main()
            
            assert result == 0
            captured = capsys.readouterr()
            assert "Pending:    2" in captured.out
            assert "Failed:     3" in captured.out
            assert "Completed:  10" in captured.out
            assert "Permanent:  1" in captured.out
            assert "Movie 1" in captured.out
            assert "Failed Movie" in captured.out
    
    def test_main_username_override(self):
        """Test that --username overrides config"""
        with patch('main.Config.load') as mock_load, \
             patch('main.run_movie_sync') as mock_run:
            
            mock_load.return_value = {
                "username": "olduser",
                "check_interval": 3600
            }
            mock_run.return_value = 0
            
            with patch('sys.argv', ['main.py', '--username', 'newuser']):
                result = main()
            
            # Verify run_movie_sync was called with overridden username
            call_args = mock_run.call_args[0][0]
            assert call_args["username"] == "newuser"
    
    def test_main_interval_override(self):
        """Test that --interval overrides config"""
        with patch('main.Config.load') as mock_load, \
             patch('main.run_movie_sync') as mock_run:
            
            mock_load.return_value = {
                "username": "testuser",
                "check_interval": 3600
            }
            mock_run.return_value = 0
            
            with patch('sys.argv', ['main.py', '--interval', '7200']):
                result = main()
            
            # Verify run_movie_sync was called with overridden interval
            call_args = mock_run.call_args[0][0]
            assert call_args["check_interval"] == 7200


class TestSetupConfiguration:
    """Test cases for setup_configuration()"""
    
    def test_setup_with_all_inputs(self, monkeypatch):
        """Test configuration setup with all custom inputs"""
        config = {
            "username": "olduser",
            "check_interval": 3600,
            "download_directory": "~/Downloads",
            "retry_interval": 3600,
            "max_retries": 5
        }
        
        # Simulate user inputs
        inputs = iter([
            'newuser',           # username
            '7200',              # check_interval
            '~/Movies',          # download_directory
            '1800',              # retry_interval
            '3'                  # max_retries
        ])
        monkeypatch.setattr('builtins.input', lambda x: next(inputs))
        
        with patch('main.Config.save') as mock_save:
            setup_configuration(config)
        
        assert config["username"] == "newuser"
        assert config["check_interval"] == 7200
        assert config["retry_interval"] == 1800
        assert config["max_retries"] == 3
        assert mock_save.called
    
    def test_setup_with_defaults(self, monkeypatch):
        """Test configuration setup keeping all defaults"""
        config = {
            "username": "testuser",
            "check_interval": 3600,
            "download_directory": "~/Downloads",
            "retry_interval": 3600,
            "max_retries": 5
        }
        
        original_config = config.copy()
        
        # Simulate user pressing enter (keep defaults)
        inputs = iter(['', '', '', '', ''])
        monkeypatch.setattr('builtins.input', lambda x: next(inputs))
        
        with patch('main.Config.save') as mock_save:
            setup_configuration(config)
        
        # Config should remain unchanged
        assert config == original_config
        assert mock_save.called
    
    def test_setup_with_partial_inputs(self, monkeypatch):
        """Test configuration setup with some inputs, some defaults"""
        config = {
            "username": "testuser",
            "check_interval": 3600,
            "download_directory": "~/Downloads",
            "retry_interval": 3600,
            "max_retries": 5
        }
        
        # Change only username and max_retries
        inputs = iter(['newuser', '', '', '', '10'])
        monkeypatch.setattr('builtins.input', lambda x: next(inputs))
        
        with patch('main.Config.save') as mock_save:
            setup_configuration(config)
        
        assert config["username"] == "newuser"
        assert config["check_interval"] == 3600  # unchanged
        assert config["max_retries"] == 10
        assert mock_save.called
    
    def test_setup_invalid_interval_ignored(self, monkeypatch):
        """Test that invalid interval input is ignored"""
        config = {
            "username": "testuser",
            "check_interval": 3600,
            "download_directory": "~/Downloads",
            "retry_interval": 3600,
            "max_retries": 5
        }
        
        # Try to set invalid (non-numeric) interval
        inputs = iter(['', 'invalid', '', '', ''])
        monkeypatch.setattr('builtins.input', lambda x: next(inputs))
        
        with patch('main.Config.save') as mock_save:
            setup_configuration(config)
        
        # Interval should remain unchanged
        assert config["check_interval"] == 3600
        assert mock_save.called


class TestRunMovieSync:
    """Test cases for run_movie_sync()"""
    
    def test_run_without_filelist_available(self, capsys):
        """Test that run_movie_sync fails gracefully without FileList"""
        config = {
            "username": "testuser",
            "check_interval": 3600
        }
        
        with patch('main.FILELIST_AVAILABLE', False):
            result = run_movie_sync(config)
        
        assert result == 1
        captured = capsys.readouterr()
        assert "Cannot start" in captured.out
    
    def test_run_creates_workers(self):
        """Test that run_movie_sync creates monitor and download workers"""
        config = {
            "username": "testuser",
            "check_interval": 60,
            "download_directory": "~/Downloads",
            "retry_interval": 3600,
            "max_retries": 5,
            "backoff_multiplier": 2.0
        }
        
        with patch('main.FILELIST_AVAILABLE', True), \
             patch('main.QueueManager') as mock_qm_class, \
             patch('main.FileListDownloader') as mock_dl, \
             patch('main.MonitorWorker') as mock_monitor, \
             patch('main.DownloadWorker') as mock_download, \
             patch('time.sleep', side_effect=KeyboardInterrupt):  # Exit immediately
            
            # Create mock instances
            mock_qm = MagicMock()
            mock_qm.get_statistics.return_value = {
                "pending": 0,
                "failed": 0,
                "completed": 0,
                "permanent_failures": 0
            }
            mock_qm_class.return_value = mock_qm
            
            mock_monitor_inst = MagicMock()
            mock_download_inst = MagicMock()
            mock_monitor.return_value = mock_monitor_inst
            mock_download.return_value = mock_download_inst
            
            try:
                run_movie_sync(config)
            except SystemExit:
                pass  # Expected from signal handler
            
            # Verify workers were created
            assert mock_monitor.called
            assert mock_download.called
            
            # Verify workers were started
            assert mock_monitor_inst.start.called
            assert mock_download_inst.start.called
