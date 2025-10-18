# Movie Sync - Automated Letterboxd to FileList.io Downloader

Automatically sync your Letterboxd watchlist with FileList.io. This tool monitors your watchlist and downloads movies via qBittorrent - all completely automated with intelligent retry mechanisms.

## ✨ Features

- 📽️ **Automatic Watchlist Sync** - Continuously monitors your Letterboxd watchlist
- 🎯 **Quality-First Selection** - Prioritizes 4K > HD > SD based on preferences
- 🔄 **Automatic Retry** - Failed downloads retry with exponential backoff
- 🤖 **Full Automation** - Multi-threaded architecture for parallel monitoring/downloading
- 🔐 **Secure Credentials** - Encrypted storage for FileList.io and qBittorrent
- 🧠 **Smart Duplicate Detection** - Uses fuzzy matching to skip existing downloads
- 💾 **Crash Recovery** - Queue persistence prevents data loss
- 🆓 **Freeleech Priority** - Optionally prefer ratio-friendly torrents
- 🧹 **Automatic Cleanup** - Optionally removes movies deleted from watchlist (with configurable grace period)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup qBittorrent

1. Install qBittorrent: `sudo apt install qbittorrent` (or download from qbittorrent.org)
2. Enable Web UI:
   - Tools → Options → Web UI
   - ☑ Enable the Web User Interface
   - Port: 8080 (default)
3. Optional: Set username/password for security

### 3. Configure

Run the configuration wizard:

```bash
python main.py --config
```

This will guide you through:
- Letterboxd username
- Monitor check interval
- Download directory
- Retry settings

Configuration files are stored in `~/.movie_sync/`:
- `config.json` - Main configuration
- `filelist_config.json` - Quality preferences and qBittorrent settings
- `credentials.enc` - Encrypted credentials (created on first run)

### 4. Run

```bash
# Start monitoring (runs continuously)
python main.py

# Show queue statistics
python main.py --stats

# Configure settings
python main.py --config
```

## 📖 How It Works

Movie Sync uses a **multi-threaded architecture**:

1. **Monitor Thread**: Checks Letterboxd watchlist periodically for new movies
2. **Download Thread**: Processes download queue with automatic retry
3. **Queue Manager**: Thread-safe queue management with JSON persistence

```
Monitor Thread              Download Thread
      │                           │
      ├─→ Check Letterboxd        ├─→ Get from queue
      ├─→ Find new movies         ├─→ Check if downloaded
      ├─→ Add to queue            ├─→ Download from FileList
      └─→ Wait interval           ├─→ Add to qBittorrent
                                  └─→ Retry on failure (exponential backoff)
```

**Key Benefits**:
- Non-blocking: Monitor continues while downloads are in progress
- Automatic retry: Failed downloads retry with increasing delays (1h → 2h → 4h → 8h → 16h)
- No data loss: All queue changes are persisted to JSON files immediately
- Graceful shutdown: Ctrl+C saves state and stops cleanly

## 🎮 Usage

### Basic Commands

```bash
# Run the application (continuously monitors and downloads)
python main.py

# Show queue statistics
python main.py --stats

# Configure settings
python main.py --config

# Override username
python main.py --username your-letterboxd-username

# Override check interval (in seconds)
python main.py --interval 1800
```

### Queue Management

View queue status:

```bash
python main.py --stats
```

Output:
```
======================================================================
📊 Queue Statistics
======================================================================

📝 Pending:    5
❌ Failed:     2
✅ Completed:  10
⛔ Permanent:  1

🔄 Movies ready for retry:
   • Movie 1 (retry #2)
   • Movie 2 (retry #1)

⛔ Permanent failures:
   • Movie 3: Not found on tracker
```

Queue files are in `~/.movie_sync/`:
- `queue_pending.json` - Movies waiting to download
- `queue_failed.json` - Failed movies with retry info
- `queue_completed.json` - Successfully downloaded movies

## ⚙️ Configuration

### Main Config (`~/.movie_sync/config.json`)

```json
{
  "username": "letterboxd-username",
  "check_interval": 3600,
  "download_directory": "/path/to/movies",
  "retry_interval": 3600,
  "max_retries": 5,
  "backoff_multiplier": 2.0
}
```

- `username` - Your Letterboxd username
- `check_interval` - Seconds between watchlist checks (default: 3600 = 1 hour)
- `download_directory` - Where movies are saved
- `retry_interval` - Base interval for retrying failed downloads (default: 3600 = 1 hour)
- `max_retries` - Maximum retry attempts before permanent failure (default: 5)
- `backoff_multiplier` - Exponential backoff multiplier for retries (default: 2.0)
- `enable_removal_cleanup` - Enable automatic cleanup of removed movies (default: false)
- `removal_grace_period` - Seconds to wait before deleting removed movies (default: 604800 = 7 days)
- `retry_interval` - Base retry interval in seconds (default: 3600 = 1 hour)
- `max_retries` - Maximum retry attempts (default: 5)
- `backoff_multiplier` - Exponential backoff multiplier (default: 2.0)

### FileList Config (`~/.movie_sync/filelist_config.json`)

```json
{
  "category_priority": [
    {"id": 6, "name": "Filme 4K", "priority": 1},
    {"id": 4, "name": "Filme HD", "priority": 2},
    {"id": 19, "name": "Filme HD-RO", "priority": 3},
    {"id": 1, "name": "Filme SD", "priority": 4}
  ],
  "download_preferences": {
    "prefer_freeleech": true,
    "minimum_seeders": 1
  },
  "qbittorrent": {
    "enabled": true,
    "host": "localhost",
    "port": 8080,
    "category": "Movies"
  }
}
```

## 🔄 Retry Mechanism

Failed downloads automatically retry with exponential backoff:

| Retry | Delay | Total Time |
|-------|-------|------------|
| 1 | 1 hour | 1 hour |
| 2 | 2 hours | 3 hours |
| 3 | 4 hours | 7 hours |
| 4 | 8 hours | 15 hours |
| 5 | 16 hours | 31 hours |

After 5 failed attempts, movies are marked as permanent failures but remain in the queue for manual review.

## 🔍 Example Output

```
======================================================================
🚀 MOVIE SYNC - Letterboxd to FileList.io
======================================================================
📺 Letterboxd user: deeplow
⏱️  Monitor interval: 3600s (60 minutes)
🔄 Retry interval: 3600s (60 minutes)
🔁 Max retries: 5
📁 Download directory: ~/Downloads

💡 Press Ctrl+C to stop gracefully
======================================================================

📋 Initializing queue manager...
⚙️  Initializing FileList downloader...
🎬 Creating monitor worker...
⬇️  Creating download worker...

🚀 Starting workers...
✅ Workers started successfully

======================================================================

🔍 Checking Letterboxd watchlist...
📺 Found 15 movies in watchlist
🆕 3 new movies detected
   ✓ Added: The Matrix (1999)
   ✓ Added: Inception (2010)
   ⊘ Skipped: Blade Runner (1982) - already downloaded
📋 Queue status: 2 pending, 0 failed, 10 completed

⬇️  Processing pending queue...
🎬 Downloading: The Matrix (1999)
   ✓ Found on FileList.io (1080p BluRay, 12.5 GB)
   ✓ Added to qBittorrent
✅ Download completed: The Matrix (1999)
```

## 🧹 Automatic Cleanup (Optional)

Movie Sync can automatically clean up movies you remove from your Letterboxd watchlist.

### How It Works

1. **Tracking**: When a movie is removed from your watchlist, it's moved to a "removed" queue
2. **Grace Period**: The movie waits for a configurable period (default: 7 days)
3. **Cleanup**: After the grace period, the following are deleted:
   - Downloaded movie files
   - Torrent file (.torrent)
   - qBittorrent entry (with files)

### Enable Cleanup

**⚠️ Cleanup is disabled by default for safety**

To enable, add to `~/.movie_sync/config.json`:

```json
{
  "enable_removal_cleanup": true,
  "removal_grace_period": 604800
}
```

### Grace Period Examples

```json
"removal_grace_period": 86400     // 1 day
"removal_grace_period": 259200    // 3 days
"removal_grace_period": 604800    // 7 days (default)
"removal_grace_period": 1209600   // 14 days
```

### Safety Features

- **Disabled by default** - Must be explicitly enabled
- **Grace period** - Time to change your mind before deletion
- **Fuzzy matching** - Uses same algorithm as download detection (85% similarity + year verification)
- **Logged operations** - All deletions are logged for review

### Example Output

```
📺 Checking Letterboxd watchlist...
   Found 50 movies in watchlist
   📤 Marked for removal: Old Movie (2010) (removed from watchlist)
   📊 Queue status: 5 pending, 2 failed, 48 completed, 1 removed

🧹 Processing 1 movie(s) for cleanup...
   🗑️  Cleaning up: Old Movie (2010)
      Removed from watchlist: 2025-10-11 15:30:22
  🗑️  Deleted movie files for: Old Movie (2010)
  🗑️  Deleted torrent file for: Old Movie (2010)
  🗑️  Removed from qBittorrent: Old Movie (2010)
      ✓ Cleanup complete for: Old Movie
```

### Monitor Removed Movies

```bash
# View removed queue
cat ~/.movie_sync/queue_removed.json | jq '.'

# Count movies waiting for cleanup
jq 'length' ~/.movie_sync/queue_removed.json
```

**For more details, see [doc/cleanup.md](doc/cleanup.md)**

## 📝 Notes

- Requires **public** Letterboxd watchlist
- FileList.io API rate limit: **150 calls/hour**
- Downloaded torrents start automatically in qBittorrent
- All queue changes are persisted immediately (no data loss on crash)
- Use Ctrl+C for graceful shutdown (saves state)
```

## 🛠️ Troubleshooting

### qBittorrent Issues

**"Could not connect to qBittorrent"**
- Ensure qBittorrent is running
- Check Web UI is enabled (Tools → Options → Web UI)
- Verify port is 8080 (or update config)

**"Login failed"**
- Credentials are stored encrypted in `~/.movie_sync/`
- Delete `qbittorrent_credentials.enc` to reset and re-enter

### FileList.io Issues

**"Invalid credentials"**
- You need your **passkey**, not your password
- Get it from: https://filelist.io/usercp.php?action=passkey

**"Rate limit reached"**
- FileList.io API limit: 150 calls/hour
- Wait an hour and try again

### Queue Issues

**Movies stuck in failed queue**
- Check `python main.py --stats` to see retry schedule
- Movies retry automatically based on exponential backoff
- After max_retries, they become permanent failures

**Want to retry a permanent failure?**
- Edit `~/.movie_sync/queue_failed.json` manually
- Set `retry_count` to 0
- Restart the application

## 📚 Documentation

Comprehensive documentation is available in the `doc/` directory:

**📑 [Documentation Index](doc/INDEX.md)** - Complete guide to all documentation

### Core Components

- **[Architecture](doc/architecture.md)** - System design, data flow, and component interaction
- **[Threading](doc/threading.md)** - Multi-threaded architecture and queue-based communication
- **[Config](doc/config.md)** - Configuration management and all available settings
- **[Credentials Manager](doc/credentials_manager.md)** - Encrypted credential storage

### Workers & Queues

- **[Queue Manager](doc/queue_manager.md)** - Thread-safe queue API and persistence
- **[Workers](doc/workers.md)** - Monitor and download worker threads

### Integration

- **[Monitor](doc/monitor.md)** - Letterboxd watchlist scraper
- **[FileList Downloader](doc/filelist_downloader.md)** - FileList.io API integration
- **[qBittorrent Manager](doc/qbittorrent_manager.md)** - qBittorrent Web UI integration

## 🔐 Security

- **FileList.io passkey** - Encrypted with Fernet (AES-128)
- **qBittorrent password** - Encrypted with Fernet (AES-128)
- **Encryption key** - Stored in `~/.movie_sync/.key` (owner read/write only)
- **Recommended**: `chmod 700 ~/.movie_sync` to restrict access

All credentials are stored in `~/.movie_sync/`:
```
~/.movie_sync/
├── .key                            # Encryption key (chmod 600)
├── filelist_credentials.enc        # FileList.io passkey (encrypted)
└── qbittorrent_credentials.enc     # qBittorrent password (encrypted)
```

To reset credentials, delete the respective `.enc` file and run again.

## 📝 Notes

- Requires **public** Letterboxd watchlist
- FileList.io API rate limit: **150 calls/hour**
- First run may take time for large watchlists
- Subsequent runs are fast (only check new movies)
- Downloaded torrents start automatically in qBittorrent
- Filter by "Movies" category or "movie_sync" tag in qBittorrent

## 🎯 Advanced Usage

### Remote qBittorrent

In `~/.movie_sync/filelist_config.json`:
```json
{
  "qbittorrent": {
    "host": "192.168.1.100",
    "port": 8080
  }
}
```

Credentials will be prompted and stored encrypted on first connection.

### Custom Quality Preferences

Want HD over 4K? Edit priorities in `~/.movie_sync/filelist_config.json`:

```json
{
  "category_priority": [
    {"id": 4, "name": "Filme HD", "priority": 1},
    {"id": 6, "name": "Filme 4K", "priority": 2},
    {"id": 19, "name": "Filme HD-RO", "priority": 3},
    {"id": 1, "name": "Filme SD", "priority": 4}
  ]
}
```

### Custom Quality Priority

Want HD over 4K? Edit priorities in `filelist_config.json`:
```json
{
  "category_priority": [
    {"id": 4, "name": "Filme HD", "priority": 1},
    {"id": 6, "name": "Filme 4K", "priority": 2}
  ]
}
```

## 📜 License

This project is for personal use. Please respect:
- Letterboxd's terms of service and rate limits
- FileList.io's API rate limits (150 calls/hour)
- Copyright laws in your jurisdiction

## 🙏 Credits

- **FileList.io** - Romanian private torrent tracker
- **Letterboxd** - Social film discovery service
- **qBittorrent** - Free and open-source BitTorrent client
