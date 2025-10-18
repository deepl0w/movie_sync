# Movie Sync Documentation Index

Complete documentation for the Movie Sync application - an automated Letterboxd to FileList.io downloader.

> **Main Documentation**: See [../README.md](../README.md) for quick start guide and basic usage.

## 📖 Table of Contents

### Getting Started

Start here if you're new to Movie Sync:

1. **[../README.md](../README.md)** - Quick start guide and basic usage
2. **[Architecture](architecture.md)** - System overview and design
3. **[Threading](threading.md)** - Multi-threaded architecture details

### Core Components

Documentation for the main components:

- **[Config](config.md)** - Configuration management and all available settings
  - Default configuration
  - Configuration file location (`~/.movie_sync/config.json`)
  - All configuration keys explained
  - Configuration wizard
  
- **[Credentials Manager](credentials_manager.md)** - Encrypted credential storage
  - Fernet encryption (AES-128)
  - Multiple service support (FileList.io, qBittorrent)
  - Interactive setup
  - Security best practices

- **[Queue Manager](queue_manager.md)** - Thread-safe queue management
  - Three queues: pending, failed, completed
  - JSON persistence
  - Atomic operations
  - Retry logic with exponential backoff

### Worker Threads

Documentation for the worker threads that do the actual work:

- **[Workers](workers.md)** - MonitorWorker and DownloadWorker
  - MonitorWorker: Checks Letterboxd watchlist periodically
  - DownloadWorker: Processes download queue with retries
  - Thread safety and coordination
  - Graceful shutdown

### Integration Components

Documentation for external service integrations:

- **[Monitor](monitor.md)** - Letterboxd watchlist scraper
  - Web scraping implementation
  - Pagination support
  - Director fetching
  - Watchlist caching
  - Rate limiting and polite scraping

- **[FileList Downloader](filelist_downloader.md)** - FileList.io API integration
  - Official API support
  - Quality selection (4K → HD → SD priority)
  - IMDB search
  - Freeleech preference
  - Rate limit handling (150 calls/hour)
  - Torrent download

- **[qBittorrent Manager](qbittorrent_manager.md)** - qBittorrent Web UI integration
  - Automatic torrent addition
  - Category management
  - Tag support
  - Connection handling
  - Auto-start support

## 🎯 Quick Reference

### File Locations

All Movie Sync files are stored in `~/.movie_sync/`:

```
~/.movie_sync/
├── config.json                 # Main configuration
├── filelist_config.json        # FileList.io quality preferences
├── credentials.enc             # Encrypted credentials (all services)
├── .key                        # Encryption key (auto-generated)
├── watchlist.json              # Cached Letterboxd watchlist
├── queue_pending.json          # Movies waiting to download
├── queue_failed.json           # Failed movies with retry info
└── queue_completed.json        # Successfully downloaded movies
```

### Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `Config` | `config.py` | Configuration management |
| `CredentialsManager` | `credentials_manager.py` | Encrypted credential storage |
| `QueueManager` | `queue_manager.py` | Thread-safe queue operations |
| `MonitorWorker` | `workers.py` | Watchlist monitoring thread |
| `DownloadWorker` | `workers.py` | Download processing thread |
| `LetterboxdWatchlistMonitor` | `monitor.py` | Letterboxd scraper |
| `FileListDownloader` | `filelist_downloader.py` | FileList.io integration |
| `QBittorrentManager` | `qbittorrent_manager.py` | qBittorrent Web UI client |

### Common Tasks

**View queue status:**
```bash
python main.py --stats
```

**Configure settings:**
```bash
python main.py --config
```

**Reset credentials:**
```bash
# Delete credentials file
rm ~/.movie_sync/credentials.enc

# Run again to re-enter
python main.py
```

**Edit queue manually:**
```bash
# Edit queue files in ~/.movie_sync/
vim ~/.movie_sync/queue_pending.json
vim ~/.movie_sync/queue_failed.json
vim ~/.movie_sync/queue_completed.json
```

## 🔧 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Main Thread                         │
│  • Loads configuration from ~/.movie_sync/                  │
│  • Initializes QueueManager (loads queue files)             │
│  • Starts MonitorWorker and DownloadWorker                  │
│  • Handles shutdown signals (SIGINT, SIGTERM)               │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐   ┌─────────────────────────────┐
│    MonitorWorker        │   │    DownloadWorker           │
│  • Check Letterboxd     │   │  • Process pending queue    │
│  • Find new movies      │   │  • Download from FileList   │
│  • Add to pending queue │   │  • Handle failures/retries  │
└─────────────────────────┘   └─────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │      QueueManager             │
              │   (Thread-Safe Queues)        │
              │  • Pending Queue              │
              │  • Failed Queue               │
              │  • Completed Queue            │
              └───────────────────────────────┘
```

## 📊 Data Flow

### New Movie Workflow

1. **MonitorWorker** checks Letterboxd watchlist
2. Finds new movie not in watchlist cache
3. Checks if movie already completed (skip if yes)
4. Adds movie to **pending queue** via QueueManager
5. **DownloadWorker** picks up movie from pending queue
6. Checks if movie already downloaded locally (fuzzy match)
7. If not downloaded:
   - Searches FileList.io API by IMDB ID
   - Selects best torrent (quality priority + seeders)
   - Downloads .torrent file
   - Adds to qBittorrent
   - Marks as **completed** in QueueManager
8. If download fails:
   - Adds to **failed queue** with retry timestamp
   - Exponential backoff: 1h → 2h → 4h → 8h → 16h
   - After 5 retries, marked as permanent failure

### Queue State Transitions

```
New Movie → Pending → Download Attempt
                         ├─→ Success → Completed
                         └─→ Failure → Failed
                                        ├─→ Retry (if retries < max) → Pending
                                        └─→ Permanent Failure (if retries >= max)
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest tests/ -v

# Specific component
pytest tests/test_queue_manager.py -v
pytest tests/test_config.py -v
pytest tests/test_credentials_manager.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

**Test Coverage**: 70% overall
- `config.py`: 100%
- `credentials_manager.py`: 99%
- `queue_manager.py`: 93%
- `monitor.py`: 90%
- `main.py`: 90%
- `qbittorrent_manager.py`: 78%
- `filelist_downloader.py`: 76%

## 🐛 Debugging

### Enable Verbose Logging

Edit Python files to increase logging verbosity:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Queue Files

All queue state is in JSON files:

```bash
# View pending movies
cat ~/.movie_sync/queue_pending.json | jq .

# View failed movies with retry info
cat ~/.movie_sync/queue_failed.json | jq .

# View completed movies
cat ~/.movie_sync/queue_completed.json | jq .
```

### Manual Queue Editing

You can manually edit queue JSON files while the app is stopped:

```bash
# Stop the app
# Edit queue files
vim ~/.movie_sync/queue_pending.json

# Restart the app (picks up changes)
python main.py
```

## 📝 Development

### Project Structure

```
movie_sync/
├── main.py                      # Entry point (314 lines)
├── config.py                    # Configuration (60 lines)
├── credentials_manager.py       # Encrypted credentials (241 lines)
├── queue_manager.py             # Thread-safe queues (150 lines)
├── workers.py                   # Worker threads (150 lines)
├── monitor.py                   # Letterboxd scraper (207 lines)
├── filelist_downloader.py       # FileList.io integration (476 lines)
├── qbittorrent_manager.py       # qBittorrent client (306 lines)
├── download_service.py          # Base downloader class
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Test configuration
├── README.md                    # Main documentation
├── doc/                         # Documentation directory
│   ├── README.md                # This file
│   ├── architecture.md
│   ├── config.md
│   ├── credentials_manager.md
│   ├── filelist_downloader.md
│   ├── monitor.md
│   ├── qbittorrent_manager.md
│   ├── queue_manager.md
│   ├── threading.md
│   └── workers.md
└── tests/                       # Test suite (111 tests)
    ├── test_config.py
    ├── test_credentials_manager.py
    ├── test_queue_manager.py
    ├── test_monitor.py
    ├── test_filelist_downloader.py
    ├── test_qbittorrent_manager.py
    ├── test_main.py
    └── conftest.py
```

### Code Style

- **PEP 8** compliant
- Type hints where appropriate
- Comprehensive docstrings
- Error handling for all external calls
- Thread-safe operations using locks

### Adding Features

1. Update relevant component (e.g., `config.py`, `queue_manager.py`)
2. Add tests in `tests/test_*.py`
3. Run test suite: `pytest tests/ -v`
4. Update documentation in `doc/`
5. Update README.md if user-facing

## 🙋 FAQ

### How often does it check my watchlist?

Default: Every 1 hour (3600 seconds). Configurable via `check_interval` in `config.json`.

### What if FileList.io is down?

Downloads fail gracefully and are automatically retried with exponential backoff.

### Can I run this on a server?

Yes! It runs headless. For qBittorrent, use `qbittorrent-nox` (headless version).

### Does it support other trackers?

Currently only FileList.io. The architecture allows adding more downloaders (extend `MovieDownloader` class).

### Will it re-download movies?

No. It uses fuzzy matching to detect existing movies and skips them.

### How do I change quality preferences?

Edit `~/.movie_sync/filelist_config.json` and adjust `category_priority`.

## 📚 Additional Resources

- [FileList.io API Documentation](https://filelist.io/api.php) (requires login)
- [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))
- [Letterboxd](https://letterboxd.com/)

## 📞 Support

For issues or questions:
1. Check the documentation in `doc/`
2. Review troubleshooting sections
3. Check test suite for examples
4. Review queue JSON files for state

---

**Last Updated**: 2024
**Version**: 2.0 (Threaded-only architecture)
