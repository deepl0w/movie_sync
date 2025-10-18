# Architecture Overview

## System Design

Movie Sync uses a multi-threaded architecture with queue-based communication and JSON persistence for reliability.

```
┌─────────────────────────────────────────────────────────────┐
│                         Main Thread                         │
│  - Initializes components                                   │
│  - Starts worker threads                                    │
│  - Handles shutdown signals (SIGINT, SIGTERM)               │
│  - Displays periodic statistics                             │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐   ┌─────────────────────────────┐
│    Monitor Thread       │   │    Download Thread          │
│    (MonitorWorker)      │   │    (DownloadWorker)         │
├─────────────────────────┤   ├─────────────────────────────┤
│ • Check Letterboxd      │   │ • Process pending queue     │
│ • Find new movies       │   │ • Check if downloaded       │
│ • Filter downloaded     │   │ • Download from FileList    │
│ • Add to pending queue  │   │ • Handle failures/retries   │
│ • Wait check_interval   │   │ • Update queues             │
└─────────────────────────┘   └─────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │      QueueManager             │
              │   (Thread-Safe Queues)        │
              ├───────────────────────────────┤
              │ • Pending Queue (FIFO)        │
              │ • Failed Queue (with retry)   │
              │ • Completed Queue (history)   │
              │ • JSON Persistence            │
              │ • Atomic Operations           │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   File System (~/.movie_sync) │
              ├───────────────────────────────┤
              │ • queue_pending.json          │
              │ • queue_failed.json           │
              │ • queue_completed.json        │
              │ • config.json                 │
              │ • watchlist.json              │
              │ • credentials.enc             │
              └───────────────────────────────┘
```

## Component Interaction

### 1. Startup Sequence

```
main.py
  ├─→ Load config from ~/.movie_sync/config.json
  ├─→ Initialize QueueManager
  │   └─→ Load queue files from disk
  ├─→ Initialize FileListDownloader
  │   ├─→ Load credentials from ~/.movie_sync/credentials.enc
  │   └─→ Connect to qBittorrent (if enabled)
  ├─→ Create MonitorWorker
  │   └─→ Pass QueueManager reference
  ├─→ Create DownloadWorker
  │   └─→ Pass QueueManager and FileListDownloader references
  ├─→ Register signal handlers (SIGINT, SIGTERM)
  ├─→ Start both worker threads
  └─→ Enter main loop (periodic statistics)
```

### 2. Monitor Workflow

```
MonitorWorker (runs every check_interval seconds)
  ├─→ Fetch watchlist from Letterboxd
  ├─→ Load previous watchlist from disk
  ├─→ Compare to find new movies
  ├─→ For each new movie:
  │   ├─→ Check if already downloaded (fuzzy match)
  │   ├─→ If not downloaded:
  │   │   └─→ QueueManager.add_to_pending(movie)
  │   └─→ If downloaded:
  │       └─→ Skip (already have it)
  ├─→ Save updated watchlist to disk
  └─→ Sleep until next check
```

### 3. Download Workflow

```
DownloadWorker (continuous loop)
  ├─→ Process Pending Queue:
  │   ├─→ QueueManager.get_next_pending()
  │   ├─→ If movie found:
  │   │   ├─→ Check if already downloaded (fuzzy match)
  │   │   ├─→ If already downloaded:
  │   │   │   └─→ QueueManager.add_to_completed(movie)
  │   │   └─→ If not downloaded:
  │   │       ├─→ FileListDownloader.download_movie(movie)
  │   │       ├─→ If success:
  │   │       │   └─→ QueueManager.add_to_completed(movie)
  │   │       └─→ If failure:
  │   │           ├─→ Calculate retry_time (exponential backoff)
  │   │           └─→ QueueManager.add_to_failed(movie, error, retry_time)
  │   └─→ If no pending movies:
  │       └─→ Wait 60 seconds
  │
  └─→ Process Retries (every 60 seconds):
      ├─→ QueueManager.get_movies_ready_for_retry(max_retries)
      └─→ For each ready movie:
          └─→ QueueManager.move_failed_to_pending(movie)
```

### 4. Shutdown Sequence

```
SIGINT/SIGTERM received
  ├─→ Set shutdown_initiated flag
  ├─→ Call MonitorWorker.stop()
  ├─→ Call DownloadWorker.stop()
  ├─→ Wait for threads (max 10 seconds)
  │   ├─→ Workers finish current operations
  │   └─→ Workers save queue state
  ├─→ Display final statistics
  └─→ Exit cleanly
```

## Data Flow

### Movie State Transitions

```
New Movie Detected
        │
        ▼
  ┌──────────┐
  │ Pending  │ ←──────────────┐
  └──────────┘                │
        │                     │
        │ Download Attempt    │ Retry (time-based)
        ▼                     │
  ┌──────────┐                │
  │  Failed  │ ───────────────┘
  └──────────┘     (retry_count < max_retries)
        │
        │ max_retries exceeded
        ▼
  ┌─────────────────┐
  │ Permanent Fail  │ (stays in Failed queue)
  └─────────────────┘

Download Attempt Success
        │
        ▼
  ┌────────────┐
  │ Completed  │ (permanent)
  └────────────┘
```

### Queue File Persistence

All queue operations trigger automatic JSON persistence:

```
Queue Operation
  ├─→ Acquire lock
  ├─→ Modify in-memory queue
  ├─→ Write to .tmp file
  ├─→ Rename to final file (atomic)
  └─→ Release lock
```

This ensures:
- No corrupted files (atomic rename)
- No data loss on crash
- Thread-safe concurrent access

## Configuration Management

### Configuration Hierarchy

1. **Default Config** (hardcoded in `config.py`)
2. **User Config** (`~/.movie_sync/config.json`)
3. **Command-Line Args** (override config values)

### Configuration Loading

```python
# Load with defaults merged
config = Config.load()

# Command-line overrides
if args.username:
    config["username"] = args.username
if args.interval:
    config["check_interval"] = args.interval
```

## Thread Safety

### QueueManager Synchronization

Each queue has dedicated locks:

```python
class QueueManager:
    def __init__(self):
        self.pending_lock = threading.Lock()
        self.failed_lock = threading.Lock()
        self.completed_lock = threading.Lock()
    
    def add_to_pending(self, movie):
        with self.pending_lock:
            # Thread-safe modification
            self.pending.append(movie)
            self._save_json(self.pending_file, self.pending)
```

### Worker Coordination

Workers communicate only through QueueManager:
- No shared state between workers
- No direct inter-thread communication
- All coordination via queues

## Error Recovery

### Crash Recovery

On startup, QueueManager loads existing queue files:
- Pending movies remain pending
- Failed movies retain retry schedules
- Completed movies stay completed
- No data loss from unexpected shutdown

### Retry Strategy

Failed downloads use exponential backoff:
- Prevents hammering the tracker
- Increases success rate over time
- Automatic retry until max_retries

### Graceful Degradation

- **Network Down**: Workers wait and retry
- **Tracker Down**: Movies added to failed queue
- **No Credentials**: Interactive prompt
- **Invalid Config**: Use defaults

## Performance Characteristics

### Resource Usage

| Resource | Usage | Notes |
|----------|-------|-------|
| Threads | 3 total | Main + Monitor + Download |
| Memory | < 50 MB | Mostly queue data |
| Disk I/O | Minimal | Only on queue changes |
| Network | Low | Periodic checks only |

### Scalability

| Metric | Limit | Bottleneck |
|--------|-------|------------|
| Queue Size | Unlimited | Disk space |
| Watchlist Size | ~1000 movies | Letterboxd pagination |
| Concurrent Downloads | 1 | Tracker rate limits |
| Check Frequency | ~60s minimum | Letterboxd rate limits |

## Security

### Credential Storage

- Encrypted using Fernet (symmetric encryption)
- Key stored separately from data
- File permissions: 0600 (owner read/write only)

### File Permissions

All files in `~/.movie_sync/`:
- Created with restrictive permissions
- Only accessible by user
- No sensitive data in plaintext

## Monitoring

### Statistics Available

```python
stats = queue_manager.get_statistics()
# Returns:
# {
#     "pending": 5,
#     "failed": 2,
#     "completed": 10,
#     "permanent_failures": 1
# }
```

### Logging

- Worker activities logged to console
- Errors logged with context
- Progress updates on state changes

## Testing Strategy

### Unit Tests
- `test_config.py` - Configuration management
- `test_credentials_manager.py` - Credential encryption
- `test_queue_manager.py` - Queue operations
- `test_filelist_downloader.py` - FileList.io API
- `test_monitor.py` - Letterboxd scraping

### Integration Tests
- `test_main.py` - End-to-end workflows
- Thread startup and shutdown
- Signal handling
- Configuration override

### Manual Testing
- Run `python main.py` with real credentials
- Test graceful shutdown (Ctrl+C)
- Test crash recovery (kill -9)
- Verify queue persistence
