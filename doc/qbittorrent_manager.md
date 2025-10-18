# qBittorrent Manager

## Overview

The `QBittorrentManager` class provides integration with the qBittorrent BitTorrent client via its Web UI API. It handles torrent management including adding torrents, checking status, and automatic client startup.

**Module**: `qbittorrent_manager.py`  
**Class**: `QBittorrentManager`  
**Dependencies**: `qbittorrent-api`, `credentials_manager`

## Features

- **Automatic Client Detection**: Checks if qBittorrent is running and attempts to start it
- **Web UI Integration**: Connects via qBittorrent's Web UI API
- **Encrypted Credentials**: Secure credential storage via `CredentialsManager`
- **Category Management**: Automatic category creation and assignment
- **Tag Support**: Apply tags to torrents for organization
- **Custom Save Paths**: Configure download locations per torrent
- **Duplicate Detection**: Gracefully handles already-existing torrents
- **Connection Retry**: Automatic reconnection on connection loss
- **Multi-Platform**: Supports both GUI and headless (nox) versions

## Prerequisites

### Install qBittorrent

**Linux (Debian/Ubuntu)**:
```bash
sudo apt install qbittorrent
# Or for headless server:
sudo apt install qbittorrent-nox
```

**macOS**:
```bash
brew install qbittorrent
```

**Windows**:
Download from https://www.qbittorrent.org/download.php

### Enable Web UI

1. Open qBittorrent
2. Go to **Tools** → **Options** (or **Preferences**)
3. Navigate to **Web UI** tab
4. Check **Enable the Web User Interface (Remote control)**
5. Set **Port**: 8080 (default)
6. (Optional) Set username and password for authentication
7. Click **OK** to save

### Install Python Library

```bash
pip install qbittorrent-api
```

## Configuration

In `~/.movie_sync/config.json`:

```json
{
  "qbittorrent": {
    "enabled": true,
    "host": "localhost",
    "port": 8080,
    "category": "Movies",
    "tags": "movie_sync,filelist",
    "save_path": null
  }
}
```

**Configuration Keys**:
- `enabled` (bool): Whether to use qBittorrent integration. Default: `true`
- `host` (str): qBittorrent Web UI hostname. Default: `"localhost"`
- `port` (int): qBittorrent Web UI port. Default: `8080`
- `category` (str): Default category for movie torrents. Default: `"Movies"`
- `tags` (str): Comma-separated tags. Default: `"movie_sync,filelist"`
- `save_path` (str or null): Custom save path, or `null` for qBittorrent default

## API Reference

### Constructor

```python
QBittorrentManager(
    host: str = "localhost",
    port: int = 8080,
    username: str = None,
    password: str = None,
    use_stored_credentials: bool = True
)
```

**Parameters**:
- `host` (str): qBittorrent Web UI host. Default: `"localhost"`
- `port` (int): qBittorrent Web UI port. Default: `8080`
- `username` (str, optional): Web UI username (or from storage)
- `password` (str, optional): Web UI password (or from storage)
- `use_stored_credentials` (bool): Use encrypted credential storage. Default: `True`

**Example**:
```python
from qbittorrent_manager import QBittorrentManager

# Use default settings with stored credentials
manager = QBittorrentManager()

# Use custom host/port
manager = QBittorrentManager(host="192.168.1.100", port=8080)

# Provide credentials directly
manager = QBittorrentManager(
    username="admin",
    password="adminpass",
    use_stored_credentials=False
)
```

### add_torrent()

```python
def add_torrent(
    self,
    torrent_path: str,
    save_path: Optional[str] = None,
    category: str = "Movies",
    tags: str = "movie_sync"
) -> bool
```

Add a torrent file to qBittorrent.

**Parameters**:
- `torrent_path` (str): Path to the `.torrent` file
- `save_path` (str, optional): Where to save downloaded files (None = qBittorrent default)
- `category` (str): Category for the torrent. Default: `"Movies"`
- `tags` (str): Comma-separated tags. Default: `"movie_sync"`

**Returns**: `bool` - `True` if torrent was added successfully, `False` otherwise

**Example**:
```python
manager = QBittorrentManager()

# Basic usage
success = manager.add_torrent("/path/to/movie.torrent")

# With custom category and save path
success = manager.add_torrent(
    torrent_path="/path/to/movie.torrent",
    save_path="/media/movies",
    category="4K Movies",
    tags="movie_sync,filelist,4k"
)

if success:
    print("✓ Torrent added to qBittorrent")
else:
    print("✗ Failed to add torrent")
```

**Behavior**:
- Automatically creates category if it doesn't exist
- Returns `True` even if torrent already exists (409 Conflict)
- Torrents start downloading immediately (not paused)
- Ensures qBittorrent is running before adding

### get_torrent_info()

```python
def get_torrent_info(self, torrent_hash: str) -> Optional[dict]
```

Get information about a specific torrent by its hash.

**Parameters**:
- `torrent_hash` (str): The torrent info hash

**Returns**: `Optional[dict]` - Torrent information, or `None` if not found:
- `name` (str): Torrent name
- `progress` (float): Download progress (0.0 to 1.0)
- `state` (str): Torrent state (e.g., "downloading", "seeding")
- `downloaded` (int): Bytes downloaded
- `size` (int): Total size in bytes
- `eta` (int): Estimated time remaining (seconds)
- `num_seeds` (int): Number of seeds connected

**Example**:
```python
manager = QBittorrentManager()

info = manager.get_torrent_info("abc123def456...")
if info:
    print(f"Name: {info['name']}")
    print(f"Progress: {info['progress'] * 100:.1f}%")
    print(f"State: {info['state']}")
    print(f"Seeds: {info['num_seeds']}")
    
    # Calculate ETA
    if info['eta'] > 0:
        eta_mins = info['eta'] // 60
        print(f"ETA: {eta_mins} minutes")
```

### list_torrents()

```python
def list_torrents(self, category: str = None) -> list
```

List all torrents, optionally filtered by category.

**Parameters**:
- `category` (str, optional): Filter by category (None = all torrents)

**Returns**: `list` - List of torrent dictionaries, each containing:
- `name` (str): Torrent name
- `progress` (float): Progress percentage (0-100)
- `state` (str): Current state
- `category` (str): Category name
- `size` (int): Total size in bytes
- `eta` (int): ETA in seconds

**Example**:
```python
manager = QBittorrentManager()

# List all torrents
all_torrents = manager.list_torrents()
print(f"Total torrents: {len(all_torrents)}")

# List only movie torrents
movies = manager.list_torrents(category="Movies")
for torrent in movies:
    print(f"{torrent['name']}: {torrent['progress']:.1f}%")

# List downloading torrents
downloading = [t for t in all_torrents if t['state'] == 'downloading']
print(f"Currently downloading: {len(downloading)}")
```

### _ensure_qbittorrent_running()

```python
def _ensure_qbittorrent_running(self) -> bool
```

Check if qBittorrent is running, attempt to start it if not.

**Returns**: `bool` - `True` if qBittorrent is accessible, `False` otherwise

**Behavior**:
1. Tries to connect to existing qBittorrent instance
2. If connection fails, attempts to start qBittorrent GUI
3. If GUI not found, attempts to start qBittorrent-nox (headless)
4. Waits up to 10 seconds for Web UI to become accessible
5. Provides helpful error messages if Web UI is not enabled

**Example**:
```python
manager = QBittorrentManager()

if manager._ensure_qbittorrent_running():
    print("qBittorrent is ready")
    # Proceed with torrent operations
else:
    print("Could not start qBittorrent")
    print("Please start it manually")
```

### _connect()

```python
def _connect(self) -> bool
```

Connect to qBittorrent Web UI.

**Returns**: `bool` - `True` if connection successful, `False` otherwise

**Error Handling**:
- `LoginFailed`: Invalid username/password
- `ConnectionError`: qBittorrent not running or Web UI disabled
- `Timeout`: Network issues

**Example**:
```python
manager = QBittorrentManager()

if manager._connect():
    print("Connected to qBittorrent")
else:
    print("Connection failed")
```

### _get_credentials()

```python
def _get_credentials(self) -> tuple
```

Get qBittorrent credentials from encrypted storage or prompt user.

**Returns**: `tuple` - `(username, password)` - Empty strings if no authentication needed

**Interactive Prompt** (if credentials not in storage):
```
=== qBittorrent Web UI Credentials ===
If your qBittorrent Web UI requires authentication, enter credentials.
Otherwise, just press Enter to skip (leave empty).

qBittorrent username (or press Enter): admin
qBittorrent password (or press Enter): ****
```

**Example**:
```python
manager = QBittorrentManager()
username, password = manager._get_credentials()

if username:
    print(f"Using authentication for user: {username}")
else:
    print("No authentication required")
```

## Usage Examples

### Basic Torrent Addition

```python
from qbittorrent_manager import QBittorrentManager

manager = QBittorrentManager()

torrent_file = "/path/to/Inception.2010.torrent"

if manager.add_torrent(torrent_file):
    print("✓ Torrent added successfully")
else:
    print("✗ Failed to add torrent")
```

### Custom Configuration

```python
manager = QBittorrentManager(
    host="localhost",
    port=8080,
    use_stored_credentials=True
)

success = manager.add_torrent(
    torrent_path="/path/to/movie.torrent",
    save_path="/media/4k-movies",
    category="4K Movies",
    tags="movie_sync,filelist,4k,hdr"
)
```

### Monitor Download Progress

```python
import time

manager = QBittorrentManager()

# Add torrent and get its hash (you'd need to parse this from the torrent file)
manager.add_torrent("/path/to/movie.torrent")

# Monitor all Movies category torrents
while True:
    movies = manager.list_torrents(category="Movies")
    
    print("\n" + "="*60)
    for torrent in movies:
        print(f"{torrent['name'][:50]}")
        print(f"  Progress: {torrent['progress']:.1f}%")
        print(f"  State: {torrent['state']}")
    
    # Check if all complete
    if all(t['progress'] >= 100 for t in movies):
        print("\n✓ All downloads complete!")
        break
    
    time.sleep(5)
```

### List All Torrents

```python
manager = QBittorrentManager()

torrents = manager.list_torrents()

print(f"Total torrents: {len(torrents)}\n")

for i, torrent in enumerate(torrents, 1):
    print(f"{i}. {torrent['name']}")
    print(f"   Category: {torrent['category']}")
    print(f"   Progress: {torrent['progress']:.1f}%")
    print(f"   State: {torrent['state']}")
    
    # Calculate size in GB
    size_gb = torrent['size'] / (1024**3)
    print(f"   Size: {size_gb:.2f} GB")
    
    print()
```

### Remote qBittorrent Server

```python
# Connect to qBittorrent on another machine
manager = QBittorrentManager(
    host="192.168.1.100",
    port=8080,
    username="admin",
    password="secret"
)

# Add torrent to remote server
manager.add_torrent(
    "/path/to/local/torrent.torrent",
    save_path="/mnt/nas/movies"  # Remote path
)
```

### Integration with FileList Downloader

```python
from filelist_downloader import FileListDownloader
from qbittorrent_manager import QBittorrentManager

# FileListDownloader will use QBittorrentManager internally
downloader = FileListDownloader(use_qbittorrent=True)

movie = {
    "title": "Inception",
    "year": 2010,
    "imdb_id": "tt1375666"
}

# This will:
# 1. Search FileList.io
# 2. Download .torrent file
# 3. Add to qBittorrent via QBittorrentManager
downloader.download_movie(movie)
```

### Standalone Test

Run the built-in test:

```bash
python qbittorrent_manager.py
```

Output:
```
qBittorrent Manager Test
============================================================

✓ qBittorrent is running and accessible

Current torrents: 3
1. Inception (2010) 1080p BluRay x264
   Progress: 45.2% | State: downloading
2. The Matrix (1999) 4K UHD
   Progress: 100.0% | State: seeding
3. Interstellar (2014) 2160p
   Progress: 12.8% | State: downloading
```

## Credentials Management

### No Authentication

If qBittorrent Web UI has no password:
```python
# Just press Enter when prompted, or:
manager = QBittorrentManager(
    username="",
    password="",
    use_stored_credentials=False
)
```

### With Authentication

If qBittorrent requires login:
```python
# Will prompt on first use and store encrypted
manager = QBittorrentManager(use_stored_credentials=True)

# Or provide directly
manager = QBittorrentManager(
    username="admin",
    password="secretpass",
    use_stored_credentials=False
)
```

### Clear Stored Credentials

```python
from credentials_manager import CredentialsManager

cm = CredentialsManager()
cm.clear_qbittorrent_credentials()

# Next time QBittorrentManager is used, it will prompt again
```

## Torrent States

qBittorrent torrents can be in various states:

| State | Description |
|-------|-------------|
| `downloading` | Actively downloading |
| `uploading` | Uploading only (complete but not seeding) |
| `pausedDL` | Paused while downloading |
| `pausedUP` | Paused while uploading |
| `queuedDL` | Queued for download |
| `queuedUP` | Queued for upload |
| `stalledDL` | Stalled (no peers) |
| `stalledUP` | Stalled while uploading |
| `checkingDL` | Checking download |
| `checkingUP` | Checking upload |
| `checkingResumeData` | Checking resume data |
| `allocating` | Allocating disk space |
| `metaDL` | Downloading metadata |
| `forcedDL` | Forced download |
| `forcedUP` | Forced upload |
| `moving` | Moving to new location |
| `error` | Error state |
| `missingFiles` | Files missing |
| `unknown` | Unknown state |

## Error Handling

### Connection Failures

```python
manager = QBittorrentManager()

if not manager._connect():
    print("Connection failed. Possible reasons:")
    print("1. qBittorrent not running")
    print("2. Web UI not enabled")
    print("3. Wrong host/port")
    print("4. Firewall blocking connection")
```

### Login Failures

```python
# If login fails, credentials are cleared
# User will be re-prompted on next attempt

manager = QBittorrentManager()
success = manager.add_torrent("/path/to/file.torrent")

# If login failed, success will be False
# Check logs for: "✗ qBittorrent login failed - check username/password"
```

### File Not Found

```python
manager = QBittorrentManager()

torrent_path = "/nonexistent/file.torrent"
success = manager.add_torrent(torrent_path)

# Output: "✗ Torrent file not found: /nonexistent/file.torrent"
# Returns: False
```

### Duplicate Torrents

```python
manager = QBittorrentManager()

# Add torrent first time
manager.add_torrent("/path/to/movie.torrent")  # Returns True

# Add same torrent again
manager.add_torrent("/path/to/movie.torrent")  # Still returns True

# Output: "ℹ Torrent already exists in qBittorrent"
```

## Testing

Run qBittorrent manager tests:

```bash
pytest tests/test_qbittorrent_manager.py -v
```

**Test Coverage**:
- Connection establishment
- Credential management
- Torrent addition
- Duplicate handling
- Category creation
- Torrent listing
- Error handling (login failures, file not found)
- Mock qBittorrent API responses

**Key Test Cases**:
```python
def test_connection_success(mock_qbt):
    """Test successful connection"""
    
def test_add_torrent_basic(mock_qbt):
    """Test basic torrent addition"""
    
def test_add_torrent_with_category(mock_qbt):
    """Test category auto-creation"""
    
def test_duplicate_torrent_handling(mock_qbt):
    """Test Conflict409Error handling"""
    
def test_list_torrents_filtered(mock_qbt):
    """Test category filtering"""
```

## Troubleshooting

### "Could not connect to qBittorrent"

**Solutions**:
1. Verify qBittorrent is running: `ps aux | grep qbittorrent`
2. Check Web UI is enabled: Tools → Options → Web UI
3. Verify port: Default is 8080
4. Test in browser: http://localhost:8080
5. Check firewall rules

### "qBittorrent login failed"

**Solutions**:
1. Clear stored credentials: `cm.clear_qbittorrent_credentials()`
2. Verify username/password in qBittorrent Web UI settings
3. Try with no authentication (leave credentials empty)
4. Restart qBittorrent

### "qBittorrent started but Web UI not accessible"

**Solutions**:
1. Open qBittorrent GUI
2. Go to **Tools** → **Options** → **Web UI**
3. Enable: **Web User Interface (Remote control)**
4. Click **OK**
5. Restart qBittorrent

### "Torrent file not found"

**Solutions**:
1. Verify file path is correct and absolute
2. Check file actually exists: `ls -la /path/to/file.torrent`
3. Verify read permissions
4. Check file extension is `.torrent`

### Torrents not starting

**Solutions**:
1. Check qBittorrent global limits (Tools → Options → Speed)
2. Verify category limits
3. Check if torrents are paused
4. Verify save path is writable
5. Check disk space

### Import Error: `ModuleNotFoundError`

**Problem**: `ModuleNotFoundError: No module named 'qbittorrentapi'`

**Solution**:
```bash
pip install qbittorrent-api

# Or install all requirements
pip install -r requirements.txt
```

### Remote Connection Issues

**Problem**: Cannot connect to remote qBittorrent

**Solutions**:
1. Verify remote access enabled in qBittorrent Web UI settings
2. Check firewall on remote machine allows port 8080
3. Use correct IP address (not localhost)
4. Test connectivity: `telnet 192.168.1.100 8080`
5. Check if authentication is required

## Performance Considerations

### Connection Pooling

The manager maintains a persistent connection:
```python
# Connection is reused across multiple operations
manager = QBittorrentManager()

for torrent_file in torrent_files:
    manager.add_torrent(torrent_file)  # Reuses same connection
```

### Batch Operations

```python
# Efficient: One manager instance for multiple torrents
manager = QBittorrentManager()
for torrent in torrents:
    manager.add_torrent(torrent)

# Inefficient: Creating new manager each time
for torrent in torrents:
    manager = QBittorrentManager()  # New connection each time
    manager.add_torrent(torrent)
```

### Auto-Reconnection

If connection is lost, manager automatically reconnects:
```python
manager = QBittorrentManager()

# Connection established
manager.add_torrent("file1.torrent")

# If qBittorrent restarts, manager reconnects automatically
manager.add_torrent("file2.torrent")  # Reconnects if needed
```

## Integration with Workers

When used with `DownloadWorker`:

```python
from workers import DownloadWorker
from filelist_downloader import FileListDownloader
from queue_manager import QueueManager

# FileListDownloader creates QBittorrentManager internally
downloader = FileListDownloader(use_qbittorrent=True)

queue_manager = QueueManager()
worker = DownloadWorker(
    queue_manager=queue_manager,
    downloader=downloader
)

worker.start()
# Worker will add torrents to qBittorrent as movies are processed
```

See [workers.md](workers.md) for more details.

## See Also

- [filelist_downloader.md](filelist_downloader.md) - FileList.io integration
- [credentials_manager.md](credentials_manager.md) - Credential encryption
- [workers.md](workers.md) - Worker thread integration
- [architecture.md](architecture.md) - System overview
