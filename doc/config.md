# Configuration Management

## Overview

The `Config` class provides centralized configuration management for Movie Sync. All configuration files are stored in `~/.movie_sync/` directory for security and consistency.

## Configuration File

**Location**: `~/.movie_sync/config.json`

The configuration file is automatically created with default values on first run.

## Default Configuration

```python
{
    "username": "",                                    # Letterboxd username
    "watchlist_file": "~/.movie_sync/watchlist.json", # Watchlist cache
    "download_queue_file": "~/.movie_sync/download_queue.json",  # Legacy queue
    "check_interval": 3600,                           # Monitor interval (seconds)
    "download_directory": "~/Downloads",              # Where movies are saved
    "retry_interval": 3600,                           # Base retry interval (seconds)
    "max_retries": 5,                                 # Maximum retry attempts
    "backoff_multiplier": 2.0,                        # Exponential backoff multiplier
    "use_threads": true                               # Enable threaded mode (always true)
}
```

## API Reference

### Config.load()

Load configuration from file or return defaults.

```python
from config import Config

config = Config.load()
```

**Returns**: Dictionary with merged configuration (defaults + user settings)

**Behavior**:
- Creates `~/.movie_sync/` directory if it doesn't exist
- Loads `config.json` if present
- Merges loaded values with defaults
- Returns defaults for missing keys

### Config.save(config)

Save configuration to file.

```python
from config import Config

config = Config.load()
config["username"] = "new_username"
config["check_interval"] = 7200
Config.save(config)
```

**Parameters**:
- `config` (dict): Configuration dictionary to save

**Behavior**:
- Creates `~/.movie_sync/` directory if needed
- Writes to `~/.movie_sync/config.json`
- Formats JSON with 2-space indentation
- Overwrites existing file

### Config.CONFIG_DIR

Path to configuration directory.

```python
from config import Config

print(Config.CONFIG_DIR)  # PosixPath('/home/user/.movie_sync')
```

## Configuration Keys

### Required Settings

#### username
**Type**: `string`  
**Default**: `""`  
**Description**: Your Letterboxd username. Required to fetch watchlist.

**Example**:
```json
{
  "username": "deeplow"
}
```

### Monitoring Settings

#### check_interval
**Type**: `integer`  
**Default**: `3600` (1 hour)  
**Description**: Seconds between watchlist checks. Minimum recommended: 300 (5 minutes).

**Example**:
```json
{
  "check_interval": 1800  // Check every 30 minutes
}
```

#### download_directory
**Type**: `string`  
**Default**: `"~/Downloads"`  
**Description**: Directory where movies are downloaded. Also used to check for existing downloads.

**Example**:
```json
{
  "download_directory": "/media/movies"
}
```

### Retry Settings

#### retry_interval
**Type**: `integer`  
**Default**: `3600` (1 hour)  
**Description**: Base interval for retry attempts. First retry happens after this many seconds.

**Example**:
```json
{
  "retry_interval": 7200  // First retry after 2 hours
}
```

#### max_retries
**Type**: `integer`  
**Default**: `5`  
**Description**: Maximum number of retry attempts before marking as permanent failure.

**Example**:
```json
{
  "max_retries": 3  // Only retry 3 times
}
```

#### backoff_multiplier
**Type**: `float`  
**Default**: `2.0`  
**Description**: Multiplier for exponential backoff. Each retry waits `retry_interval * (multiplier ^ retry_count)` seconds.

**Example**:
```json
{
  "backoff_multiplier": 1.5  // Slower backoff
}
```

**Retry Schedule Examples**:

With `retry_interval=3600` and `backoff_multiplier=2.0`:
- Retry 1: 1 hour
- Retry 2: 2 hours  
- Retry 3: 4 hours
- Retry 4: 8 hours
- Retry 5: 16 hours

With `retry_interval=1800` and `backoff_multiplier=1.5`:
- Retry 1: 30 minutes
- Retry 2: 45 minutes
- Retry 3: 1 hour 8 minutes
- Retry 4: 1 hour 41 minutes
- Retry 5: 2 hours 32 minutes

### Legacy Settings

#### watchlist_file
**Type**: `string`  
**Default**: `"~/.movie_sync/watchlist.json"`  
**Description**: Where the watchlist cache is stored. Generally not changed.

#### download_queue_file
**Type**: `string`  
**Default**: `"~/.movie_sync/download_queue.json"`  
**Description**: Legacy queue file (not used in threaded mode). Queue is now managed by separate JSON files.

#### use_threads
**Type**: `boolean`  
**Default**: `true`  
**Description**: Always true in current version. Single-threaded mode has been removed.

## Usage Examples

### Basic Configuration

```python
from config import Config

# Load configuration
config = Config.load()

# Check if username is configured
if not config.get("username"):
    print("Please configure your Letterboxd username")
    config["username"] = input("Username: ")
    Config.save(config)

# Access settings
interval = config["check_interval"]
download_dir = config["download_directory"]
```

### Interactive Configuration

```python
from config import Config

def setup_config():
    config = Config.load()
    
    # Username
    username = input(f"Letterboxd username [{config.get('username', '')}]: ")
    if username:
        config["username"] = username
    
    # Check interval
    print(f"Current check interval: {config['check_interval']}s")
    interval = input("Check interval in seconds [3600]: ")
    if interval and interval.isdigit():
        config["check_interval"] = int(interval)
    
    # Save
    Config.save(config)
    print("✓ Configuration saved")

setup_config()
```

### Configuration Override

```python
from config import Config

# Load base configuration
config = Config.load()

# Override from command line arguments
import sys
if len(sys.argv) > 1:
    config["username"] = sys.argv[1]
if len(sys.argv) > 2:
    config["check_interval"] = int(sys.argv[2])

# Use configuration
print(f"Monitoring {config['username']} every {config['check_interval']}s")
```

## Error Handling

The Config class handles errors gracefully:

- **Missing config file**: Returns defaults
- **Invalid JSON**: Prints error and returns defaults
- **Missing keys**: Defaults used for missing values
- **File write errors**: Prints error message

Example error output:
```
Error loading config: Expecting property name enclosed in double quotes: line 5 column 3 (char 102)
```

## File Structure

```
~/.movie_sync/
├── config.json                    # Main configuration
├── filelist_config.json          # FileList.io settings
├── watchlist.json                # Watchlist cache
├── queue_pending.json            # Pending downloads
├── queue_failed.json             # Failed downloads
├── queue_completed.json          # Completed downloads
└── *_credentials.enc             # Encrypted credentials
```

## Migration from Old Versions

If upgrading from a version that stored config in the project directory:

```bash
# Create new config directory
mkdir -p ~/.movie_sync

# Move old config files
mv config.json ~/.movie_sync/ 2>/dev/null
mv filelist_config.json ~/.movie_sync/ 2>/dev/null
mv watchlist.json ~/.movie_sync/ 2>/dev/null

# The application will automatically use the new location
```

## Best Practices

1. **Don't store passwords**: Credentials are managed separately by `CredentialsManager`
2. **Use absolute paths**: For `download_directory` to avoid confusion
3. **Reasonable intervals**: Don't check Letterboxd too frequently (respect rate limits)
4. **Backup config**: Keep a backup of `~/.movie_sync/config.json`
5. **Test changes**: After modifying config, verify with `python main.py --stats`

## Testing

The configuration system is tested in `tests/test_config.py`:
- Loading defaults
- Loading from file
- Saving configuration
- Handling invalid JSON
- Merging with defaults
