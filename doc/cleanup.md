# Cleanup Service Documentation

## Overview
The Cleanup Service automatically tracks and removes movies that are no longer in your Letterboxd watchlist. This feature helps maintain a clean download library by removing movies you've unmarked from your watchlist.

## Configuration

Add these settings to your `~/.movie_sync/config.json`:

```json
{
  "enable_removal_cleanup": false,
  "removal_grace_period": 604800
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_removal_cleanup` | boolean | `false` | Enable/disable automatic cleanup (disabled by default) |
| `removal_grace_period` | integer | `604800` | Grace period in seconds before deletion (default: 7 days) |

**⚠️ IMPORTANT**: Cleanup is **disabled by default** for safety. You must explicitly enable it in your config.

## How It Works

### 1. Tracking Removed Movies
When the monitor worker detects that a movie is no longer in your watchlist:
- The movie is moved to a "removed" queue (`queue_removed.json`)
- A timestamp is recorded (`removed_at`)
- The movie is removed from the completed queue

### 2. Grace Period
Movies in the removed queue wait for the configured grace period before deletion. This gives you time to:
- Re-add the movie to your watchlist if you changed your mind
- Manually restore the movie from the removed queue
- Verify the removal was intentional

**Default grace period**: 7 days (604800 seconds)

### 3. Cleanup Process
When cleanup is **enabled**, the CleanupWorker runs every hour and:
1. Checks for movies past their grace period
2. For each movie ready for deletion:
   - Deletes downloaded movie files (using fuzzy matching)
   - Deletes the .torrent file
   - Removes the torrent from qBittorrent (with files)
3. Removes the movie from the removed queue

## File Structure

### Queue Files
All queue files are stored in `~/.movie_sync/`:

- `queue_pending.json` - Movies waiting to be downloaded
- `queue_failed.json` - Movies that failed to download
- `queue_completed.json` - Successfully downloaded movies
- `queue_removed.json` - Movies removed from watchlist (waiting for cleanup)

### Removed Queue Format
```json
[
  {
    "id": "film-12345",
    "title": "Movie Title",
    "year": 2020,
    "removed_at": 1729234567,
    "status": "removed"
  }
]
```

## Safety Features

### 1. Disabled by Default
Cleanup is **disabled by default** to prevent accidental deletions. You must explicitly enable it.

### 2. Grace Period
The default 7-day grace period gives you time to review removals before they're deleted.

### 3. Fuzzy Matching
The cleanup service uses the same fuzzy matching algorithm as download detection:
- Normalizes titles (lowercase, spaces→dots, removes special chars)
- Requires 85% similarity threshold
- Verifies year matches when available
- Prevents false matches

### 4. Logging
All cleanup operations are logged with:
- What was deleted (files, torrents, qBittorrent entries)
- When the movie was removed from watchlist
- Any errors encountered

## Usage Examples

### Enable Cleanup
Edit `~/.movie_sync/config.json`:
```json
{
  "enable_removal_cleanup": true,
  "removal_grace_period": 604800
}
```

### Change Grace Period
Set different grace periods:

```json
{
  "removal_grace_period": 259200    // 3 days
  "removal_grace_period": 86400     // 1 day
  "removal_grace_period": 1209600   // 14 days
}
```

### Manually Check Removed Movies
```bash
# View removed queue
cat ~/.movie_sync/queue_removed.json | jq '.'

# Check what would be deleted
cat ~/.movie_sync/queue_removed.json | jq '.[] | {title, removed_at}'
```

### Calculate Time Until Deletion
```python
import json
import time
from datetime import datetime

with open('~/.movie_sync/queue_removed.json') as f:
    removed = json.load(f)

grace_period = 604800  # 7 days

for movie in removed:
    removed_at = movie['removed_at']
    delete_at = removed_at + grace_period
    time_left = delete_at - time.time()
    
    print(f"{movie['title']}: {time_left / 86400:.1f} days until deletion")
```

## Worker Thread

### CleanupWorker
The cleanup worker is a separate thread that:
- Runs every hour (configurable via `check_interval`)
- Only performs deletions if `enable_removal_cleanup` is True
- Processes all movies past their grace period
- Logs all cleanup operations

### Thread Lifecycle
```
┌─────────────────────────────────────────┐
│ MonitorWorker                           │
│ - Detects removed movies                │
│ - Adds to removed queue                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ queue_removed.json                      │
│ - Movies waiting for deletion           │
│ - Timestamp: removed_at                 │
└──────────────┬──────────────────────────┘
               │ (after grace period)
               ▼
┌─────────────────────────────────────────┐
│ CleanupWorker (if enabled)              │
│ - Deletes movie files                   │
│ - Deletes torrent files                 │
│ - Removes from qBittorrent              │
└─────────────────────────────────────────┘
```

## API Reference

### QueueManager Methods

#### `mark_movies_as_removed(current_watchlist_ids: List[str]) -> int`
Mark movies as removed if they're no longer in the watchlist.

**Parameters:**
- `current_watchlist_ids`: List of movie IDs currently in watchlist

**Returns:** Number of movies marked as removed

#### `get_movies_ready_for_deletion(grace_period: int) -> List[Dict]`
Get movies from removed queue ready for deletion.

**Parameters:**
- `grace_period`: Grace period in seconds

**Returns:** List of movies past their grace period

#### `remove_from_removed_queue(movie_id: str) -> bool`
Remove a movie from the removed queue.

**Parameters:**
- `movie_id`: ID of the movie to remove

**Returns:** True if movie was found and removed

#### `restore_removed_movie(movie_id: str) -> bool`
Restore a removed movie back to pending queue.

**Parameters:**
- `movie_id`: ID of the movie to restore

**Returns:** True if movie was found and restored

### CleanupService Methods

#### `cleanup_movie(movie: Dict, delete_files: bool, delete_torrent: bool, remove_from_qbt: bool) -> Dict`
Clean up all traces of a movie.

**Parameters:**
- `movie`: Movie dictionary with title and year
- `delete_files`: Whether to delete downloaded files
- `delete_torrent`: Whether to delete torrent file
- `remove_from_qbt`: Whether to remove from qBittorrent

**Returns:** Dictionary with cleanup results

#### `get_cleanup_preview(movie: Dict) -> Dict[str, List[str]]`
Preview what would be deleted (dry run).

**Parameters:**
- `movie`: Movie dictionary with title and year

**Returns:** Dictionary with lists of files/torrents that would be deleted

## Troubleshooting

### Movies Not Being Deleted
1. Check if cleanup is enabled: `jq '.enable_removal_cleanup' ~/.movie_sync/config.json`
2. Check grace period hasn't passed: Compare `removed_at` timestamp with current time
3. Check logs for errors during cleanup

### Wrong Movies Being Deleted
This should be prevented by fuzzy matching, but if it happens:
1. Disable cleanup immediately: Set `enable_removal_cleanup` to `false`
2. Check the fuzzy matching threshold (85% similarity + year verification)
3. Report the issue with movie title and filename

### Restoring a Deleted Movie
If a movie was deleted but you want it back:
1. Re-add the movie to your Letterboxd watchlist
2. Wait for the next monitor check (or restart the service)
3. The movie will be re-queued for download

### Manually Prevent Deletion
If you want to keep a removed movie:
1. Stop the service
2. Edit `~/.movie_sync/queue_removed.json`
3. Remove the movie entry
4. Restart the service

Or use the Python API:
```python
from queue_manager import QueueManager

qm = QueueManager()
qm.restore_removed_movie("film-12345")  # Moves back to pending queue
```

## Best Practices

1. **Start with cleanup disabled** - Monitor the removed queue for a few weeks to understand the pattern
2. **Use a longer grace period initially** - Start with 14+ days to be safe
3. **Regular backups** - Even with fuzzy matching, backup important movies
4. **Review removed queue weekly** - Check `queue_removed.json` for unexpected removals
5. **Test with non-critical movies first** - Enable cleanup and test with movies you don't mind re-downloading

## Examples

### Example Configuration (Conservative)
```json
{
  "enable_removal_cleanup": true,
  "removal_grace_period": 1209600,  // 14 days
  "check_interval": 3600,
  "retry_interval": 3600,
  "max_retries": 5
}
```

### Example Configuration (Aggressive)
```json
{
  "enable_removal_cleanup": true,
  "removal_grace_period": 259200,  // 3 days
  "check_interval": 1800,
  "retry_interval": 3600,
  "max_retries": 5
}
```

### Monitor Logs for Cleanup Activity
```bash
# Run the service and watch for cleanup messages
python main.py | grep -E "Cleaning up|Deleted|Marked for removal"
```

Example output:
```
📤 Marked for removal: Old Movie (2010) (removed from watchlist)
🧹 Processing 1 movie(s) for cleanup...
   🗑️  Cleaning up: Old Movie (2010)
      Removed from watchlist: 2025-10-11 15:30:22
  🗑️  Deleted movie files for: Old Movie (2010)
  🗑️  Deleted torrent file for: Old Movie (2010)
  🗑️  Removed from qBittorrent: Old Movie (2010)
      ✓ Cleanup complete for: Old Movie
```
