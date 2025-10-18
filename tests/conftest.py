"""Pytest configuration and shared fixtures"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def config_dir(temp_dir):
    """Create a temporary config directory"""
    config_path = temp_dir / ".movie_sync"
    config_path.mkdir(parents=True, exist_ok=True)
    return config_path


@pytest.fixture
def sample_movie():
    """Sample movie data for testing"""
    return {
        "id": "12345",
        "title": "The Matrix (1999)",
        "slug": "the-matrix",
        "url": "https://letterboxd.com/film/the-matrix/",
        "year": "1999",
        "director": "Lana Wachowski, Lilly Wachowski",
        "imdb_id": "tt0133093",
        "added_at": 1609459200
    }


@pytest.fixture
def sample_watchlist(sample_movie):
    """Sample watchlist for testing"""
    return [
        sample_movie,
        {
            "id": "67890",
            "title": "Inception (2010)",
            "slug": "inception",
            "url": "https://letterboxd.com/film/inception/",
            "year": "2010",
            "director": "Christopher Nolan",
            "imdb_id": "tt1375666",
            "added_at": 1609545600
        }
    ]


@pytest.fixture
def sample_torrent_result():
    """Sample FileList.io torrent search result"""
    return {
        "name": "The.Matrix.1999.2160p.UHD.BluRay.x265-B0MBARDiERS",
        "size": "15.2 GB",
        "seeders": 42,
        "leechers": 3,
        "download_link": "https://filelist.io/download.php?id=123456",
        "id": "123456",
        "category": 6,  # Filme 4K
        "freeleech": 1,
        "doubleup": 0
    }


@pytest.fixture
def sample_filelist_config():
    """Sample FileList configuration"""
    return {
        "category_priority": [
            {"id": 6, "name": "Filme 4K", "priority": 1},
            {"id": 4, "name": "Filme HD", "priority": 2},
            {"id": 19, "name": "Filme HD-RO", "priority": 3},
            {"id": 1, "name": "Filme SD", "priority": 4}
        ],
        "download_preferences": {
            "prefer_freeleech": True,
            "prefer_doubleup": False,
            "minimum_seeders": 1
        },
        "qbittorrent": {
            "enabled": True,
            "host": "localhost",
            "port": 8080,
            "category": "Movies",
            "tags": "movie_sync,filelist",
            "save_path": None
        }
    }


@pytest.fixture
def mock_qbt_client(mocker):
    """Mock qBittorrent API client"""
    mock_client = mocker.MagicMock()
    mock_client.app.version = "v4.5.0"
    mock_client.torrents_add.return_value = "Ok."
    mock_client.torrents_categories.return_value = {}
    mock_client.torrents_info.return_value = []
    return mock_client


@pytest.fixture
def json_file_helper(temp_dir):
    """Helper to create temporary JSON files"""
    def _create_json_file(filename: str, data: Dict[str, Any]) -> Path:
        file_path = temp_dir / filename
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return file_path
    
    return _create_json_file
