# FileList Downloader

## Overview

The `FileListDownloader` class handles searching, selecting, and downloading movie torrents from FileList.io, a Romanian private torrent tracker. It integrates with the FileList.io API for searching and provides intelligent quality selection based on configurable priorities.

**Module**: `filelist_downloader.py`  
**Class**: `FileListDownloader`  
**Extends**: `MovieDownloader` (from `download_service.py`)

## Features

- **API Integration**: Official FileList.io API support with authentication
- **Smart Quality Selection**: Prioritized category search (4K → HD → SD)
- **IMDB Search**: Primary search by IMDB ID with title fallback
- **Freeleech Preference**: Optionally prefer freeleech/doubleup torrents
- **Seeder Filtering**: Minimum seeder requirements for healthy downloads
- **qBittorrent Integration**: Automatic torrent addition to qBittorrent
- **Encrypted Credentials**: Secure storage via `CredentialsManager`
- **Rate Limit Handling**: Graceful handling of API rate limits (150 calls/hour)
- **Error Recovery**: Comprehensive error handling and retry logic

## Configuration

### Category Priority

Movies are searched in order of quality preference:

```python
"category_priority": [
    {"id": 6, "name": "Filme 4K", "priority": 1},
    {"id": 4, "name": "Filme HD", "priority": 2},
    {"id": 19, "name": "Filme HD-RO", "priority": 3},
    {"id": 1, "name": "Filme SD", "priority": 4}
]
```

### Download Preferences

```python
"download_preferences": {
    "prefer_freeleech": True,      # Prefer freeleech torrents
    "prefer_doubleup": False,       # Prefer doubleup torrents
    "minimum_seeders": 1            # Minimum seeders required
}
```

### qBittorrent Configuration

```python
"qbittorrent": {
    "enabled": True,
    "host": "localhost",
    "port": 8080,
    "category": "Movies",
    "tags": "movie_sync,filelist",
    "save_path": null  # null = qBittorrent default
}
```

## API Reference

### Constructor

```python
FileListDownloader(
    config_file: str = None,
    use_qbittorrent: bool = True,
    torrent_dir: str = None
)
```

**Parameters**:
- `config_file` (str, optional): Path to config JSON file. Default: `~/.movie_sync/config.json`
- `use_qbittorrent` (bool): Whether to use qBittorrent integration. Default: `True`
- `torrent_dir` (str, optional): Directory to save .torrent files. Default: `~/Downloads`

**Example**:
```python
from filelist_downloader import FileListDownloader

downloader = FileListDownloader()
```

### download_movie()

```python
def download_movie(self, movie: Dict) -> bool
```

Main method to download a movie. Searches FileList.io, selects best torrent, and adds to qBittorrent or saves .torrent file.

**Parameters**:
- `movie` (dict): Movie metadata with keys:
  - `title` (str): Movie title
  - `year` (int): Release year
  - `imdb_id` (str, optional): IMDB ID (e.g., "tt1234567")
  - `director` (str, optional): Director name

**Returns**: `bool` - `True` if download successful, `False` otherwise

**Example**:
```python
movie = {
    "title": "Inception",
    "year": 2010,
    "imdb_id": "tt1375666",
    "director": "Christopher Nolan"
}

success = downloader.download_movie(movie)
if success:
    print("Movie queued for download")
```

**Process Flow**:
1. Search FileList.io API by IMDB ID (or title if no IMDB ID)
2. Filter results by minimum seeders
3. Select best torrent based on quality priority and seeders
4. Download .torrent file
5. Add to qBittorrent or save to torrent directory

### _search_movie()

```python
def _search_movie(self, movie: Dict) -> List[Dict]
```

Search for a movie on FileList.io using the official API.

**Parameters**:
- `movie` (dict): Movie metadata (see `download_movie()`)

**Returns**: `List[Dict]` - List of torrent results (max 10), each containing:
- `name` (str): Torrent name
- `size` (str): File size
- `seeders` (int): Number of seeders
- `leechers` (int): Number of leechers
- `download_link` (str): Download URL
- `id` (str): Torrent ID
- `category` (int): Category ID
- `freeleech` (int): Freeleech status (0 or 1)
- `doubleup` (int): Doubleup status (0 or 1)

**Example**:
```python
results = downloader._search_movie({
    "title": "The Matrix",
    "imdb_id": "tt0133093"
})

for torrent in results:
    print(f"{torrent['name']} - {torrent['seeders']} seeders")
```

### _select_best_torrent()

```python
def _select_best_torrent(self, results: List[Dict]) -> Optional[Dict]
```

Select the best torrent based on quality priority, seeders, and preferences.

**Selection Strategy**:
1. Filter by minimum seeders
2. Group by category priority (quality tier)
3. Select highest quality tier available
4. Within tier, optionally prefer freeleech/doubleup
5. Select torrent with most seeders

**Parameters**:
- `results` (List[Dict]): List of torrent results from `_search_movie()`

**Returns**: `Optional[Dict]` - Best torrent, or `None` if no suitable torrent found

**Example**:
```python
results = downloader._search_movie(movie)
best = downloader._select_best_torrent(results)

if best:
    print(f"Selected: {best['name']}")
    print(f"Quality: Category {best['category']}")
    print(f"Seeders: {best['seeders']}")
```

### _download_torrent_file()

```python
def _download_torrent_file(self, torrent_id: str, movie_title: str) -> Optional[str]
```

Download a .torrent file from FileList.io.

**Parameters**:
- `torrent_id` (str): The FileList.io torrent ID
- `movie_title` (str): Movie title (for filename)

**Returns**: `Optional[str]` - Path to downloaded .torrent file, or `None` if failed

**Example**:
```python
torrent_path = downloader._download_torrent_file(
    torrent_id="123456",
    movie_title="Inception"
)

if torrent_path:
    print(f"Saved to: {torrent_path}")
```

### _get_credentials()

```python
def _get_credentials(self) -> bool
```

Get FileList.io API credentials (username + passkey) from storage or prompt user.

**Returns**: `bool` - `True` if credentials available, `False` otherwise

**Interactive Prompt** (if credentials not found):
```
=== FileList.io API Credentials Required ===
You need your username and passkey (not password!) from FileList.io
To get your passkey:
  1. Log in to https://filelist.io
  2. Go to your profile settings
  3. Copy your API passkey

Username: your_username
Passkey: abc123xyz...
```

## Usage Examples

### Basic Download

```python
from filelist_downloader import FileListDownloader

downloader = FileListDownloader()

movie = {
    "title": "The Shawshank Redemption",
    "year": 1994,
    "imdb_id": "tt0111161"
}

if downloader.download_movie(movie):
    print("✓ Movie download started")
else:
    print("✗ Download failed")
```

### Custom Configuration

```python
from filelist_downloader import FileListDownloader

# Use custom config file
downloader = FileListDownloader(
    config_file="/path/to/custom_config.json",
    use_qbittorrent=True,
    torrent_dir="~/Torrents"
)

movie = {
    "title": "Interstellar",
    "year": 2014,
    "imdb_id": "tt0816692",
    "director": "Christopher Nolan"
}

downloader.download_movie(movie)
```

### Manual Search and Selection

```python
downloader = FileListDownloader()

# Search for torrents
movie = {"title": "Dune", "year": 2021, "imdb_id": "tt1160419"}
results = downloader._search_movie(movie)

print(f"Found {len(results)} torrents:")
for i, torrent in enumerate(results, 1):
    print(f"{i}. {torrent['name']}")
    print(f"   Seeders: {torrent['seeders']}, Size: {torrent['size']}")
    if torrent['freeleech']:
        print(f"   [FREELEECH]")

# Let the system select best
best = downloader._select_best_torrent(results)
if best:
    print(f"\nBest choice: {best['name']}")
```

### Without qBittorrent

```python
# Just download .torrent files without qBittorrent integration
downloader = FileListDownloader(use_qbittorrent=False)

movie = {"title": "The Matrix", "year": 1999, "imdb_id": "tt0133093"}

if downloader.download_movie(movie):
    # .torrent file saved to ~/Downloads/
    print("Torrent file ready for manual import")
```

### Batch Processing

```python
downloader = FileListDownloader()

movies = [
    {"title": "Inception", "year": 2010, "imdb_id": "tt1375666"},
    {"title": "The Dark Knight", "year": 2008, "imdb_id": "tt0468569"},
    {"title": "Interstellar", "year": 2014, "imdb_id": "tt0816692"}
]

for movie in movies:
    print(f"\nProcessing: {movie['title']}")
    success = downloader.download_movie(movie)
    print(f"Status: {'✓' if success else '✗'}")
```

## API Rate Limits

FileList.io API has strict rate limits:

- **150 calls per hour** per user
- **Rate limit resets** every hour
- **Failed authentications** can temporarily block access (1 hour)

**Best Practices**:
```python
import time

downloader = FileListDownloader()

for movie in large_movie_list:
    success = downloader.download_movie(movie)
    
    if not success:
        # Check if rate limited
        print("Pausing to respect rate limits...")
        time.sleep(30)  # Wait 30 seconds between failures
    else:
        time.sleep(2)  # Small delay between successful requests
```

## Error Handling

The downloader handles various error conditions:

### API Errors

```python
# 429 - Rate Limit
# Output: "✗ Rate limit reached (150 calls/hour). Please wait before trying again."

# 403 - Authentication Failed
# Output: "✗ Invalid credentials: ..."
# Action: Credentials cleared, user will be re-prompted

# 400 - Invalid Parameters
# Output: "✗ Invalid search parameters: ..."
```

### Network Errors

```python
try:
    success = downloader.download_movie(movie)
except Exception as e:
    # All exceptions are caught internally
    # Check return value instead
    if not success:
        print("Download failed, check logs")
```

### Missing Credentials

```python
# If credentials not in storage, user is prompted interactively
downloader = FileListDownloader()
downloader.download_movie(movie)
# Prompts for username and passkey if not found
```

## Quality Selection Logic

### Category Priority

Torrents are selected in this order:

1. **Filme 4K** (Category 6) - Highest priority
2. **Filme HD** (Category 4) - Second priority
3. **Filme HD-RO** (Category 19) - Third priority (Romanian)
4. **Filme SD** (Category 1) - Lowest priority

### Within Same Category

If multiple torrents in the same category:

1. **Filter** by minimum seeders (default: 1)
2. **Prefer** freeleech if enabled (default: True)
3. **Prefer** doubleup if enabled (default: False)
4. **Select** torrent with most seeders

### Example Selection

```
Available torrents:
- [4K] Inception (2010) - 10 seeders - FREELEECH
- [4K] Inception (2010) - 15 seeders
- [HD] Inception (2010) - 50 seeders - FREELEECH

Selection: [4K] Inception (2010) - 15 seeders
Reason: 4K is highest priority, most seeders in 4K category
Note: Freeleech preference only applies within same seeder count
```

## File Organization

### Torrent Files

Default location: `~/Downloads/`

Naming pattern: `{sanitized_title}_{torrent_id}.torrent`

Example:
```
~/Downloads/
  Inception_2010_123456.torrent
  The_Matrix_1999_234567.torrent
```

### qBittorrent Integration

When qBittorrent is enabled:
- **Category**: "Movies" (configurable)
- **Tags**: "movie_sync,filelist"
- **Save Path**: qBittorrent default (or custom path)
- **Auto-start**: Yes (torrents start downloading immediately)

## Credentials Management

FileList.io requires:
- **Username**: Your FileList.io username
- **Passkey**: API passkey (NOT password)

**Getting Your Passkey**:
1. Log in to https://filelist.io
2. Navigate to Profile → Settings
3. Find "API Passkey" or "Passkey" section
4. Copy the passkey string

**Storage**:
- Encrypted using `CredentialsManager`
- Stored in `~/.movie_sync/credentials.enc`
- Permissions: 0600 (owner read/write only)

**Clearing Credentials**:
```python
from credentials_manager import CredentialsManager

cm = CredentialsManager()
cm.clear_filelist_credentials()
# Next download will prompt for new credentials
```

## Testing

Run the FileList downloader tests:

```bash
pytest tests/test_filelist_downloader.py -v
```

**Test Coverage**:
- API search with IMDB ID
- API search with title fallback
- Quality selection logic
- Freeleech preference
- Seeder filtering
- Torrent file download
- qBittorrent integration
- Error handling (rate limits, invalid credentials)
- Mock FileList.io API responses

**Key Test Cases**:
```python
def test_search_by_imdb(mock_api):
    """Test IMDB-based search"""
    
def test_quality_priority_selection(mock_torrents):
    """Test 4K > HD > SD priority"""
    
def test_freeleech_preference(mock_torrents):
    """Test freeleech preference within same quality"""
    
def test_rate_limit_handling(mock_api):
    """Test graceful rate limit error handling"""
```

## Troubleshooting

### No torrents found

**Problem**: Search returns 0 results

**Solutions**:
1. Verify IMDB ID is correct (format: `tt1234567`)
2. Try title-based search (remove IMDB ID)
3. Check if movie exists on FileList.io
4. Verify category priorities include relevant categories

### Rate limit errors

**Problem**: "Rate limit reached (150 calls/hour)"

**Solutions**:
1. Wait 1 hour for rate limit to reset
2. Reduce search frequency
3. Add delays between requests
4. Cache search results

### Authentication failures

**Problem**: "Invalid credentials" or "Too many failed authentications"

**Solutions**:
1. Verify username and passkey (not password!)
2. Clear credentials: `cm.clear_filelist_credentials()`
3. Re-enter credentials when prompted
4. Wait 1 hour if temporarily blocked
5. Check FileList.io account status

### qBittorrent connection failed

**Problem**: "Could not connect to qBittorrent"

**Solutions**:
1. Ensure qBittorrent is running
2. Enable Web UI in qBittorrent settings
3. Verify host and port (default: localhost:8080)
4. Check qBittorrent credentials
5. Try manually: `http://localhost:8080` in browser

### Low quality torrents selected

**Problem**: SD torrents selected instead of HD/4K

**Solutions**:
1. Check category priorities in config
2. Verify HD/4K categories enabled
3. Adjust `minimum_seeders` (might be filtering out HD)
4. Check if HD/4K torrents actually exist for that movie

### Import errors

**Problem**: `ModuleNotFoundError: No module named 'qbittorrentapi'`

**Solutions**:
```bash
# Install required dependencies
pip install qbittorrent-api requests

# Or install all project requirements
pip install -r requirements.txt
```

## Performance Considerations

### API Call Optimization

```python
# GOOD: Batch process with delays
for movie in movies:
    downloader.download_movie(movie)
    time.sleep(2)  # Respect rate limits

# BAD: Rapid-fire requests
for movie in movies:
    downloader.download_movie(movie)  # Will hit rate limit
```

### Search Performance

- **IMDB search**: ~1-2 seconds
- **Title search**: ~2-3 seconds (less accurate)
- **Rate limit**: 150 calls/hour = ~1 call per 24 seconds

### Optimization Tips

1. **Use IMDB IDs** when available (faster, more accurate)
2. **Cache results** if searching same movies multiple times
3. **Batch process** with appropriate delays
4. **Monitor rate limits** and implement backoff
5. **Filter movies** before searching (avoid duplicate searches)

## Integration with Workers

When used in threaded mode with `DownloadWorker`:

```python
from workers import DownloadWorker
from filelist_downloader import FileListDownloader
from queue_manager import QueueManager

queue_manager = QueueManager()
downloader = FileListDownloader()

worker = DownloadWorker(
    queue_manager=queue_manager,
    downloader=downloader,
    check_interval=30  # Check for new movies every 30 seconds
)

worker.start()  # Start download worker thread
```

See [workers.md](workers.md) and [threading.md](threading.md) for more details.

## See Also

- [qbittorrent_manager.md](qbittorrent_manager.md) - qBittorrent integration details
- [credentials_manager.md](credentials_manager.md) - Credential encryption
- [workers.md](workers.md) - Worker thread integration
- [architecture.md](architecture.md) - System overview
