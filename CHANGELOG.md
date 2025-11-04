# Changelog

All notable changes to Movie Sync project.

## [0.2.0] - 2025-xx-xx

### Changes

- Downloaded items are now moved to the downloaded queue only after they are truly downloaded in the torrent client (instead of when they are added)
- Merged  `download_directory` from `config.json` and `qbittorrent.save_path` from `filelist_config.json`, now only `download_directory` is used
- Fixed torrent deletion from qbittorrent

## [0.1.0] - 2025-10-21

### 🎉 Initial Release

A fully automated Letterboxd to FileList.io movie downloader with multi-threaded architecture, web interface, and cleanup management.

### ✨ Core Features

**Multi-Threaded Architecture**
- **MonitorWorker** - Continuously monitors Letterboxd watchlist for new movies
- **DownloadWorker** - Processes download queue with automatic retry logic
- **CleanupWorker** - Handles automatic removal of movies deleted from watchlist
- **QueueManager** - Thread-safe queue management with JSON persistence (4 queues: pending, failed, completed, removed)
- **Graceful Shutdown** - Clean stop on Ctrl+C with state preservation

**Web Interface** 🆕
- Real-time queue monitoring with live statistics
- Interactive movie management (retry, skip, force delete)
- Responsive design with Letterboxd-inspired gradient UI
- Mobile-optimized layout with bottom navigation
- Live log streaming with color-coded severity levels
- Configuration editor with validation
- Manual watchlist refresh trigger
- Auto-refresh for real-time updates

**Letterboxd Integration**
- Watchlist scraping with pagination support
- Complete movie metadata (title, year, director, IMDB ID)
- Watchlist caching for efficient new movie detection
- Configurable check intervals
- Title normalization for accurate matching (handles special characters, years in titles)

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
- Torrent hash tracking for cleanup operations

**Queue Management**
- Four separate queues: pending, failed, completed, removed
- JSON file persistence (crash recovery)
- Atomic file operations (no corruption)
- Exponential backoff retry (1h → 2h → 4h → 8h → 16h)
- Maximum retry limit (default: 5)
- Permanent failure tracking
- Grace period for removed movies (default: 7 days)
- Queue statistics and monitoring

**Automatic Cleanup Service** 🆕
- Monitors completed movies for removal from watchlist
- Configurable grace period before deletion (default: 7 days)
- Multi-level cleanup:
  - Downloaded video files (via fuzzy filename matching)
  - Torrent files from FileList downloads folder
  - Active torrents from qBittorrent (stop and delete)
- Detailed cleanup logging and error handling
- Optional force delete via web interface
- Safe fallback when qBittorrent is unavailable

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
- Cleanup settings (enable/disable, grace period)
- Configurable file paths (downloads, torrents)

**Smart Features**
- Fuzzy matching for duplicate detection
- Already-downloaded movie filtering
- Quality tier prioritization
- Seeder-based torrent selection
- Automatic retry scheduling
- Checkpoint recovery on restart
- Title normalization (handles parentheses, special chars)

### 📦 Components

**Core Files**
- `main.py` - Application entry point with threaded execution
- `config.py`  Configuration management
- `credentials_manager.py` - Encrypted credential storage
- `queue_manager.py` - Thread-safe queue operations
- `workers.py` - MonitorWorker, DownloadWorker, and CleanupWorker threads
- `logger_config.py` - Centralized logging configuration

**Integration Modules**
- `monitor.py` - Letterboxd watchlist scraper
- `filelist_downloader.py` - FileList.io API client
- `qbittorrent_manager.py` - qBittorrent Web UI client
- `download_service.py` - Base downloader interface
- `cleanup_service.py` - File and torrent cleanup management

**Web Interface** 🆕
- `web_interface.py` - Flask-based web dashboard
- `templates/index.html` - Single-page application template
- `static/css/style.css` - Responsive Letterboxd-style design
- `static/js/app.js` - Interactive queue management and live updates

**Configuration Files** (in `~/.movie_sync/`)
- `config.json` - Main application settings
- `filelist_config.json` - Quality preferences and qBittorrent config
- `credentials.enc` - Encrypted credentials (auto-generated)
- `.key` - Encryption key (auto-generated)

**Queue Files** (in `~/.movie_sync/`)
- `queue_pending.json` - Movies waiting to download
- `queue_failed.json` - Failed movies with retry info
- `queue_completed.json` - Successfully downloaded movies
- `queue_removed.json` - Movies marked for deletion (with grace period)
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
- `cleanup.md` - Cleanup service documentation
- `web_interface_structure.md` - Web dashboard architecture

### 🧪 Testing

**Comprehensive test suite** (240 tests passing, 85%+ coverage):
- `tests/test_config.py` - Configuration tests
- `tests/test_credentials_manager.py` - Encryption tests
- `tests/test_queue_manager.py` - Queue operations (16 tests)
- `tests/test_monitor.py` - Watchlist scraping
- `tests/test_filelist_downloader.py` - API integration
- `tests/test_qbittorrent_manager.py` - qBittorrent client
- `tests/test_download_service.py` - Download service interface
- `tests/test_cleanup_service.py` - Cleanup operations (11 tests)
- `tests/test_web_interface.py` - Web dashboard and API endpoints (46 tests)
- `tests/test_workers.py` - Worker thread integration
- `tests/test_workers_extended.py` - Extended worker scenarios
- `tests/test_main.py` - Application integration

**Test Infrastructure:**
- `tests/conftest.py` - Shared fixtures and mocks
- `pytest.ini` - Test configuration
- HTML coverage reports in `htmlcov/`

### 📋 Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
cryptography>=41.0.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.21.0
qbittorrent-api>=2024.9.67
flask>=2.3.0
pytest>=7.4.0
pytest-cov>=4.1.0
```

### 🚀 Usage

```bash
# Run the application (command line only)
python main.py

# Run with web interface (recommended)
python main.py --web

# View queue statistics
python main.py --stats

# Interactive configuration
python main.py --config

# Override settings
python main.py --username deeplow --interval 1800
```

### 🌐 Web Interface

Access the dashboard at `http://localhost:5000` (when running with `--web`)

**Features:**
- Real-time statistics (pending, failed, completed, removed)
- Queue management with clickable cards
- Movie actions: Retry, Skip, Force Delete
- Live log viewing with auto-scroll
- Configuration editor
- Manual watchlist refresh
- Mobile-responsive design
- Letterboxd-inspired gradient UI with parallax effects

### 🧹 Cleanup Service

**Automatic Cleanup:**
- Movies removed from watchlist are marked for deletion
- Grace period (default: 7 days) before actual cleanup
- Cleans up:
  - Downloaded video files
  - .torrent files from downloads folder
  - Active torrents in qBittorrent

**Manual Cleanup:**
- Force delete via web interface
- Immediate cleanup (bypasses grace period)
- Detailed cleanup results logging

### 🔧 Requirements

- Python 3.8+
- qBittorrent with Web UI enabled
- FileList.io account with API access
- Public Letterboxd watchlist

---

## Future Enhancements

Potential improvements for future versions:

- Priority queue for specific movies
- Bandwidth throttling and scheduling
- Download scheduling (off-peak hours)
- Support for other torrent trackers
- Multiple Letterboxd list support
- Dark/light theme toggle
- Advanced search and filtering in web interface
- Download progress tracking with qBittorrent integration
- Historical statistics and charts
