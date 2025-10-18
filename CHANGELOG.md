# Changelog

All notable changes to Movie Sync project.

## [0.1.0] - 2025-10-18

### 🎉 Initial Release

A fully automated Letterboxd to FileList.io movie downloader with multi-threaded architecture.

### ✨ Core Features

**Multi-Threaded Architecture**
- **MonitorWorker** - Continuously monitors Letterboxd watchlist for new movies
- **DownloadWorker** - Processes download queue with automatic retry logic
- **QueueManager** - Thread-safe queue management with JSON persistence
- **Graceful Shutdown** - Clean stop on Ctrl+C with state preservation

**Letterboxd Integration**
- Watchlist scraping with pagination support
- Complete movie metadata (title, year, director, IMDB ID)
- Watchlist caching for efficient new movie detection
- Configurable check intervals

**FileList.io Integration**
- Official FileList.io REST API support
- IMDB ID-based search for accurate matching
- Quality-based torrent selection (4K > HD > SD)
- Freeleech preference option
- Minimum seeder filtering
- Rate limit handling (150 calls/hour)
- Automatic passkey authentication

**qBittorrent Integration**
- Automatic torrent addition via Web UI API
- Auto-start qBittorrent if not running
- Category-based organization ("Movies")
- Tag support for filtering ("movie_sync", "filelist")
- Custom save paths
- Connection retry logic

**Queue Management**
- Three separate queues: pending, failed, completed
- JSON file persistence (crash recovery)
- Atomic file operations (no corruption)
- Exponential backoff retry (1h → 2h → 4h → 8h → 16h)
- Maximum retry limit (default: 5)
- Permanent failure tracking
- Queue statistics and monitoring

**Security**
- Encrypted credential storage (Fernet/AES-128)
- File permissions enforcement (0600)
- Multi-service support (FileList.io, qBittorrent)
- No plaintext passwords in config files
- Secure key storage in `~/.movie_sync/.key`

**Configuration**
- Centralized config in `~/.movie_sync/`
- Interactive configuration wizard
- Default values with smart fallbacks
- Quality priority customization
- Retry behavior configuration

**Smart Features**
- Fuzzy matching for duplicate detection
- Already-downloaded movie filtering
- Quality tier prioritization
- Seeder-based torrent selection
- Automatic retry scheduling
- Checkpoint recovery on restart

### 📦 Components

**Core Files**
- `main.py` (314 lines) - Application entry point with threaded execution
- `config.py` (60 lines) - Configuration management
- `credentials_manager.py` (241 lines) - Encrypted credential storage
- `queue_manager.py` (150 lines) - Thread-safe queue operations
- `workers.py` (150 lines) - MonitorWorker and DownloadWorker threads

**Integration Modules**
- `monitor.py` (207 lines) - Letterboxd watchlist scraper
- `filelist_downloader.py` (476 lines) - FileList.io API client
- `qbittorrent_manager.py` (306 lines) - qBittorrent Web UI client
- `download_service.py` - Base downloader interface

**Configuration Files** (in `~/.movie_sync/`)
- `config.json` - Main application settings
- `filelist_config.json` - Quality preferences and qBittorrent config
- `credentials.enc` - Encrypted credentials (auto-generated)
- `.key` - Encryption key (auto-generated)

**Queue Files** (in `~/.movie_sync/`)
- `queue_pending.json` - Movies waiting to download
- `queue_failed.json` - Failed movies with retry info
- `queue_completed.json` - Successfully downloaded movies
- `watchlist.json` - Cached Letterboxd watchlist

### 📚 Documentation

**Comprehensive docs in `doc/` directory:**
- `INDEX.md` - Documentation table of contents
- `architecture.md` - System design and data flow
- `threading.md` - Multi-threaded architecture details
- `config.md` - Configuration reference
- `credentials_manager.md` - Security and encryption
- `monitor.md` - Letterboxd integration
- `filelist_downloader.md` - FileList.io API usage
- `qbittorrent_manager.md` - qBittorrent integration
- `queue_manager.md` - Queue API reference
- `workers.md` - Worker thread documentation

### 🧪 Testing

**Complete test suite** (111 tests, 70% coverage):
- `tests/test_config.py` - Configuration tests
- `tests/test_credentials_manager.py` - Encryption tests
- `tests/test_queue_manager.py` - Queue operations
- `tests/test_monitor.py` - Watchlist scraping
- `tests/test_filelist_downloader.py` - API integration
- `tests/test_qbittorrent_manager.py` - qBittorrent client
- `tests/test_main.py` - Application integration

### 📋 Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
cryptography>=41.0.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.21.0
qbittorrent-api>=2024.9.67
pytest>=7.4.0
pytest-cov>=4.1.0
```

### 🚀 Usage

```bash
# Run the application
python main.py

# View queue statistics
python main.py --stats

# Interactive configuration
python main.py --config

# Override settings
python main.py --username deeplow --interval 1800
```

### 🔧 Requirements

- Python 3.8+
- qBittorrent with Web UI enabled
- FileList.io account with API access
- Public Letterboxd watchlist

---

## Future Enhancements

Potential improvements for future versions:

- Web dashboard for queue monitoring
- Email/Telegram notifications
- Priority queue for specific movies
- Multiple FileList.io accounts (round-robin)
- Bandwidth throttling
- Download scheduling (off-peak hours)
- Support for other torrent trackers
- Plex/Jellyfin integration
- Subtitle download integration
- Multiple Letterboxd list support
