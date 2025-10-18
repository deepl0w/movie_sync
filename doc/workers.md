# Worker Threads

## Overview

The worker threads handle the core functionality of Movie Sync: monitoring the Letterboxd watchlist and downloading movies. Both workers run as daemon threads and can be stopped gracefully.

## MonitorWorker

### Purpose
Periodically checks the Letterboxd watchlist for new movies and adds them to the pending queue.

### Initialization

```python
from workers import MonitorWorker
from queue_manager import QueueManager

qm = QueueManager()

monitor = MonitorWorker(
    username="letterboxd_username",
    queue_manager=qm,
    check_interval=3600,  # Check every hour
    watchlist_file="~/.movie_sync/watchlist.json"  # Optional
)
```

### Parameters

- **username** (str): Letterboxd username to monitor
- **queue_manager** (QueueManager): Shared queue manager instance
- **check_interval** (int): Seconds between watchlist checks (default: 3600)
- **watchlist_file** (str, optional): Path to save watchlist for comparison

### Operation

1. Fetches current watchlist from Letterboxd
2. Compares with previously saved watchlist
3. Identifies new movies
4. Filters out already downloaded movies (fuzzy matching)
5. Adds new movies to pending queue
6. Saves updated watchlist
7. Waits for check_interval seconds
8. Repeats until stopped

### Methods

#### start()
Start the monitor thread (daemon).

```python
monitor.start()
```

#### stop()
Signal the thread to stop.

```python
monitor.stop()
monitor.join(timeout=10)  # Wait up to 10 seconds
```

#### run()
Main thread loop (called automatically by start(), do not call directly).

### Example Output

```
🔍 Checking Letterboxd watchlist...
📺 Found 15 movies in watchlist
🆕 3 new movies detected
   ✓ Added: The Matrix (1999)
   ✓ Added: Inception (2010)
   ⊘ Skipped: Blade Runner (1982) - already downloaded
📋 Queue status: 2 pending, 0 failed, 10 completed
⏰ Next check in 3600 seconds (1.0 hours)
```

## DownloadWorker

### Purpose
Processes the pending queue, downloads movies, and handles retry logic for failures.

### Initialization

```python
from workers import DownloadWorker
from queue_manager import QueueManager
from filelist_downloader import FileListDownloader

qm = QueueManager()
downloader = FileListDownloader(queue_file=None, use_qbittorrent=True)

download_worker = DownloadWorker(
    queue_manager=qm,
    downloader=downloader,
    download_dir="~/Downloads",
    retry_interval=3600,      # Base retry interval (1 hour)
    max_retries=5,            # Maximum retry attempts
    backoff_multiplier=2.0    # Exponential backoff multiplier
)
```

### Parameters

- **queue_manager** (QueueManager): Shared queue manager instance
- **downloader** (FileListDownloader): FileList.io downloader instance
- **download_dir** (str): Directory to check for existing downloads
- **retry_interval** (int): Base retry interval in seconds (default: 3600)
- **max_retries** (int): Maximum retry attempts (default: 5)
- **backoff_multiplier** (float): Exponential backoff multiplier (default: 2.0)

### Operation

1. **Process Pending Queue**:
   - Get next movie from pending queue
   - Check if already downloaded (fuzzy matching)
   - Attempt download via FileList.io
   - On success: Add to completed queue
   - On failure: Add to failed queue with retry schedule

2. **Process Retries** (every 60 seconds):
   - Get failed movies ready for retry
   - Move them back to pending queue
   - Exponential backoff increases wait time

3. Repeats until stopped

### Retry Logic

#### Exponential Backoff Formula

```
retry_delay = base_interval * (multiplier ^ retry_count)
```

#### Example Schedule (base=3600s, multiplier=2.0):

| Retry | Calculation | Delay | Total Time |
|-------|-------------|-------|------------|
| 1 | 3600 × 2^0 | 1 hour | 1 hour |
| 2 | 3600 × 2^1 | 2 hours | 3 hours |
| 3 | 3600 × 2^2 | 4 hours | 7 hours |
| 4 | 3600 × 2^3 | 8 hours | 15 hours |
| 5 | 3600 × 2^4 | 16 hours | 31 hours |

Maximum delay is capped at 24 hours.

### Fuzzy Matching

The worker uses fuzzy string matching to detect already downloaded movies:

- **Threshold**: 85% similarity
- **Year Bonus**: +10% if year appears in filename
- **Recursive Search**: Checks all video files in download directory

#### Supported Video Extensions
`.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`

### Methods

#### start()
Start the download worker thread (daemon).

```python
download_worker.start()
```

#### stop()
Signal the thread to stop.

```python
download_worker.stop()
download_worker.join(timeout=10)  # Wait up to 10 seconds
```

#### run()
Main thread loop (called automatically by start(), do not call directly).

### Example Output

```
⬇️  Processing pending queue...
🎬 Downloading: The Matrix (1999)
   ✓ Found on FileList.io (1080p BluRay, 12.5 GB)
   ✓ Added to qBittorrent
✅ Download completed: The Matrix (1999)

⬇️  Processing pending queue...
🎬 Downloading: Rare Movie (2015)
   ✗ Not found on FileList.io
❌ Added to failed queue (retry in 1.0 hours)

🔄 Checking for retries...
   ↻ Retrying: Rare Movie (2015) (attempt 2/5)
```

## Thread Safety

Both workers share the `QueueManager` instance which provides thread-safe operations:

- **Locks**: Each queue has its own lock
- **Atomic Operations**: All queue modifications are atomic
- **No Race Conditions**: Properly synchronized access

## Graceful Shutdown

Both workers can be stopped gracefully:

```python
import signal
import sys

def signal_handler(sig, frame):
    print("Stopping workers...")
    monitor.stop()
    download_worker.stop()
    
    monitor.join(timeout=10)
    download_worker.join(timeout=10)
    
    print("Shutdown complete")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

## Configuration

Worker behavior is controlled by configuration in `~/.movie_sync/config.json`:

```json
{
  "username": "letterboxd_username",
  "check_interval": 3600,
  "download_directory": "~/Downloads",
  "retry_interval": 3600,
  "max_retries": 5,
  "backoff_multiplier": 2.0
}
```

## Error Handling

### Monitor Worker Errors
- **Network Errors**: Logged and retried on next check
- **Invalid Watchlist**: Logged and continues with empty list
- **Queue Full**: Movies are added as space becomes available

### Download Worker Errors
- **Download Failures**: Added to failed queue with retry
- **Not Found**: Added to failed queue with retry
- **Network Errors**: Added to failed queue with retry
- **Max Retries Exceeded**: Movie marked as permanent failure

## Performance Considerations

### Resource Usage
- **CPU**: Minimal (only during active operations)
- **Memory**: Small (queue data + downloader state)
- **Network**: Periodic HTTP requests to Letterboxd and FileList.io

### Rate Limiting
- Monitor respects `check_interval` to avoid spamming Letterboxd
- Download worker processes movies sequentially
- Retry backoff prevents hammering the tracker

## Testing

See `tests/test_queue_manager.py` for queue manager tests.

Worker threads are tested indirectly through:
- Integration tests in `tests/test_main.py`
- Manual testing with `python main.py`

Note: Direct worker testing is challenging due to daemon thread nature and external dependencies (Letterboxd, FileList.io).
