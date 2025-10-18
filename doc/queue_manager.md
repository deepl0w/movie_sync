# Queue Manager

## Overview

The `QueueManager` class provides thread-safe queue management for the Movie Sync application. It manages three separate queues with JSON persistence for crash recovery.

## Queue Files

All queue files are stored in `~/.movie_sync/`:

- **queue_pending.json** - Movies waiting to be downloaded
- **queue_failed.json** - Movies that failed with retry information
- **queue_completed.json** - Successfully downloaded movies

## Architecture

### Thread Safety

Each queue has its own lock to prevent race conditions:
- `pending_lock` - Protects pending queue operations
- `failed_lock` - Protects failed queue operations  
- `completed_lock` - Protects completed queue operations

### Atomic Writes

All JSON writes use atomic operations:
1. Write to temporary file (`.tmp` extension)
2. Rename to final filename (atomic operation in POSIX)
3. This prevents corrupted files if the program crashes during write

## API Reference

### Initialization

```python
from queue_manager import QueueManager

qm = QueueManager()
```

Automatically loads existing queue files from disk or creates empty queues.

### Pending Queue Operations

#### add_to_pending(movie)
Add a movie to the pending queue.

```python
success = qm.add_to_pending({
    "id": "123",
    "title": "The Matrix",
    "year": "1999"
})
# Returns: True if added, False if duplicate or already completed
```

#### get_next_pending()
Pop the next movie from the pending queue (FIFO).

```python
movie = qm.get_next_pending()
# Returns: Movie dict or None if queue is empty
```

### Failed Queue Operations

#### add_to_failed(movie, error, retry_after)
Add a movie to the failed queue with retry information.

```python
import time

retry_after = time.time() + 3600  # Retry in 1 hour

qm.add_to_failed(
    movie={
        "id": "123",
        "title": "The Matrix",
        "year": "1999"
    },
    error="Not found on tracker",
    retry_after=retry_after
)
```

This automatically:
- Increments `retry_count`
- Updates `last_error` 
- Sets `retry_after` timestamp
- Sets `failed_at` timestamp (first failure only)

#### get_movies_ready_for_retry(max_retries)
Get movies ready to retry based on time and retry count.

```python
ready_movies = qm.get_movies_ready_for_retry(max_retries=5)
# Returns: List of movies where current_time >= retry_after and retry_count < max_retries
```

#### move_failed_to_pending(movie)
Move a failed movie back to the pending queue for retry.

```python
qm.move_failed_to_pending(movie)
```

#### get_permanent_failures(max_retries)
Get movies that have exceeded max retry attempts.

```python
failures = qm.get_permanent_failures(max_retries=5)
# Returns: List of movies where retry_count >= max_retries
```

#### reset_failed_movie(movie_id)
Reset a failed movie's retry count (manual intervention).

```python
qm.reset_failed_movie("123")
```

### Completed Queue Operations

#### add_to_completed(movie)
Mark a movie as successfully downloaded.

```python
qm.add_to_completed({
    "id": "123",
    "title": "The Matrix",
    "year": "1999"
})
```

This automatically:
- Adds movie to completed queue with timestamp
- Removes from failed queue if present
- Prevents re-adding to pending queue

### Statistics

#### get_statistics()
Get current queue statistics.

```python
stats = qm.get_statistics()
# Returns: {
#     "pending": 5,
#     "failed": 2,
#     "completed": 10,
#     "permanent_failures": 1
# }
```

### Maintenance

#### cleanup_old_completed(days)
Remove completed entries older than specified days.

```python
qm.cleanup_old_completed(days=30)
```

## Queue File Format

### Pending Queue (queue_pending.json)

```json
[
  {
    "id": "123",
    "title": "The Matrix",
    "year": "1999",
    "slug": "the-matrix",
    "imdb_id": "tt0133093"
  }
]
```

### Failed Queue (queue_failed.json)

```json
[
  {
    "id": "123",
    "title": "The Matrix",
    "year": "1999",
    "slug": "the-matrix",
    "imdb_id": "tt0133093",
    "retry_count": 2,
    "last_error": "Not found on tracker",
    "retry_after": 1760813282.5,
    "failed_at": 1760806482.5
  }
]
```

### Completed Queue (queue_completed.json)

```json
[
  {
    "id": "123",
    "title": "The Matrix",
    "year": "1999",
    "slug": "the-matrix",
    "imdb_id": "tt0133093",
    "completed_at": 1760813282.5
  }
]
```

## Error Handling

- **Duplicate Prevention**: Movies are identified by `id` field
- **Completed Protection**: Completed movies cannot be re-added to pending
- **Thread Safety**: All operations are protected by locks
- **File Corruption**: Invalid JSON files are logged and reset to empty queues

## Usage Example

```python
from queue_manager import QueueManager
import time

# Initialize
qm = QueueManager()

# Add movies to pending
qm.add_to_pending({"id": "1", "title": "Movie 1", "year": "2020"})
qm.add_to_pending({"id": "2", "title": "Movie 2", "year": "2021"})

# Process pending
movie = qm.get_next_pending()
if movie:
    try:
        # Attempt download...
        download_success = download_movie(movie)
        
        if download_success:
            qm.add_to_completed(movie)
        else:
            retry_after = time.time() + 3600
            qm.add_to_failed(movie, "Download failed", retry_after)
    except Exception as e:
        retry_after = time.time() + 3600
        qm.add_to_failed(movie, str(e), retry_after)

# Check for retries
ready = qm.get_movies_ready_for_retry(max_retries=5)
for movie in ready:
    qm.move_failed_to_pending(movie)

# Get statistics
stats = qm.get_statistics()
print(f"Pending: {stats['pending']}, Failed: {stats['failed']}")
```

## Testing

See `tests/test_queue_manager.py` for comprehensive test coverage including:
- Duplicate prevention
- Thread safety
- Retry logic
- Persistence and recovery
- Statistics accuracy
