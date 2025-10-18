# Credentials Manager

## Overview

The `CredentialsManager` class provides secure, encrypted storage for sensitive credentials (API keys, passwords, etc.). All credentials are encrypted using Fernet (AES-128) symmetric encryption.

## Features

- **Encryption**: Uses `cryptography.fernet` for strong encryption
- **Multi-service**: Store credentials for multiple services independently
- **Automatic key management**: Generates and stores encryption key securely
- **File permissions**: Sets restrictive permissions (0600) on sensitive files
- **Simple API**: Easy to save and retrieve credentials

## File Storage

**Location**: `~/.movie_sync/`

```
~/.movie_sync/
├── .key                           # Encryption key (chmod 600)
├── filelist_credentials.enc       # FileList.io credentials
├── qbittorrent_credentials.enc    # qBittorrent credentials
└── *_credentials.enc              # Any other service credentials
```

## API Reference

### Initialization

```python
from credentials_manager import CredentialsManager

# Use default directory (~/.movie_sync)
cm = CredentialsManager()

# Use custom directory
cm = CredentialsManager(config_dir="/path/to/config")
```

**Parameters**:
- `config_dir` (optional): Directory to store credentials. Defaults to `~/.movie_sync`

### save_credentials(service, username, password)

Save encrypted credentials for a service.

```python
cm.save_credentials(
    service="filelist",
    username="myuser",
    password="my_api_key_12345"
)
```

**Parameters**:
- `service` (str): Service identifier (e.g., "filelist", "qbittorrent")
- `username` (str): Username or user identifier
- `password` (str): Password, API key, or passkey

**File created**: `~/.movie_sync/{service}_credentials.enc`

**Security**:
- Credentials are encrypted before writing
- File permissions set to 0600 (owner read/write only)

### get_credentials(service)

Retrieve decrypted credentials for a service.

```python
username, password = cm.get_credentials("filelist")

if username and password:
    print(f"User: {username}")
else:
    print("Credentials not found")
```

**Parameters**:
- `service` (str): Service identifier

**Returns**: `Tuple[Optional[str], Optional[str]]`
- `(username, password)` if found
- `(None, None)` if not found or decryption failed

**Error handling**:
- Returns `(None, None)` on decryption errors
- Returns `(None, None)` if file doesn't exist

### clear_credentials(service)

Delete credentials for a service.

```python
cm.clear_credentials("filelist")
```

**Parameters**:
- `service` (str): Service identifier

**Behavior**:
- Deletes `{service}_credentials.enc` file
- Does nothing if file doesn't exist

### credentials_exist(service)

Check if credentials exist for a service.

```python
if cm.credentials_exist("filelist"):
    print("Credentials found")
else:
    print("Need to set up credentials")
```

**Parameters**:
- `service` (str): Service identifier

**Returns**: `bool`
- `True` if credentials file exists
- `False` otherwise

### list_services()

List all services with stored credentials.

```python
services = cm.list_services()
print(f"Credentials stored for: {', '.join(services)}")
```

**Returns**: `List[str]`
- List of service identifiers
- Empty list if no credentials stored

**Example output**: `["filelist", "qbittorrent"]`

## Usage Examples

### Basic Usage

```python
from credentials_manager import CredentialsManager

cm = CredentialsManager()

# Save credentials
cm.save_credentials(
    service="filelist",
    username="myuser",
    password="abc123def456"
)

# Retrieve credentials
user, pass = cm.get_credentials("filelist")
print(f"Username: {user}")
```

### Interactive Credential Setup

```python
from credentials_manager import CredentialsManager

def setup_filelist_credentials():
    cm = CredentialsManager()
    
    if cm.credentials_exist("filelist"):
        print("✓ FileList.io credentials already configured")
        return
    
    print("FileList.io API Setup")
    print("=" * 40)
    print("Get your passkey from: https://filelist.io/usercp.php?action=passkey")
    print()
    
    username = input("Username: ").strip()
    passkey = input("Passkey: ").strip()
    
    if username and passkey:
        cm.save_credentials("filelist", username, passkey)
        print("✓ Credentials saved and encrypted")
    else:
        print("✗ Credentials not saved (empty input)")

setup_filelist_credentials()
```

### Credential Validation

```python
from credentials_manager import CredentialsManager

def get_or_prompt_credentials(service):
    """Get credentials from storage or prompt user"""
    cm = CredentialsManager()
    
    # Try to load from storage
    username, password = cm.get_credentials(service)
    
    if username and password:
        return username, password
    
    # Prompt for credentials
    print(f"\n{service.title()} credentials not found")
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    
    if username and password:
        save = input("Save credentials? (y/n): ").lower()
        if save == 'y':
            cm.save_credentials(service, username, password)
            print("✓ Credentials saved")
    
    return username, password

# Usage
user, pwd = get_or_prompt_credentials("qbittorrent")
```

### Managing Multiple Services

```python
from credentials_manager import CredentialsManager

cm = CredentialsManager()

# Save credentials for multiple services
cm.save_credentials("filelist", "user1", "key123")
cm.save_credentials("qbittorrent", "admin", "password")
cm.save_credentials("custom_api", "apiuser", "token456")

# List all services
services = cm.list_services()
print(f"Configured services: {services}")
# Output: ['filelist', 'qbittorrent', 'custom_api']

# Check specific service
if cm.credentials_exist("filelist"):
    user, key = cm.get_credentials("filelist")
    print(f"FileList user: {user}")
```

### Reset Credentials

```python
from credentials_manager import CredentialsManager

def reset_service_credentials(service):
    """Clear and re-enter credentials"""
    cm = CredentialsManager()
    
    # Clear existing credentials
    cm.clear_credentials(service)
    print(f"✓ Cleared {service} credentials")
    
    # Prompt for new credentials
    username = input(f"{service} username: ")
    password = input(f"{service} password: ")
    
    cm.save_credentials(service, username, password)
    print(f"✓ New {service} credentials saved")

# Usage
reset_service_credentials("filelist")
```

## Security Considerations

### Encryption

- **Algorithm**: Fernet (symmetric encryption using AES in CBC mode with HMAC)
- **Key size**: 128-bit AES key
- **Authentication**: HMAC for integrity verification
- **Rotation**: Each encryption includes a timestamp

### File Permissions

Encryption key file (`.key`) is created with mode `0600`:
```python
os.chmod(self.key_file, 0o600)  # Only owner can read/write
```

Credentials files are created with mode `0600` by default on most systems.

### Best Practices

1. **Restrict directory access**:
   ```bash
   chmod 700 ~/.movie_sync
   ```

2. **Never commit the encryption key**:
   - The `.key` file should never be in version control
   - Add to `.gitignore`: `~/.movie_sync/.key`

3. **Backup encryption key securely**:
   - Store `.key` file in secure location
   - Without it, credentials cannot be decrypted

4. **Don't share encrypted files**:
   - Even though encrypted, don't share `*_credentials.enc` files
   - Each user should have their own credentials

5. **Use strong passwords**:
   - FileList.io passkey: Use the generated passkey (not your account password)
   - qBittorrent: Use a strong unique password

## Error Handling

The class handles errors gracefully:

```python
cm = CredentialsManager()

# File doesn't exist
user, pwd = cm.get_credentials("nonexistent")
# Returns: (None, None)

# Corrupted file
user, pwd = cm.get_credentials("corrupted_service")
# Returns: (None, None) and logs error

# Delete non-existent
cm.clear_credentials("nonexistent")
# Does nothing (no error)
```

## Migration from Plaintext

If you previously stored credentials in plaintext:

```python
from credentials_manager import CredentialsManager
import json

# Load old plaintext credentials
with open("old_credentials.json") as f:
    old_creds = json.load(f)

# Migrate to encrypted storage
cm = CredentialsManager()
for service, creds in old_creds.items():
    cm.save_credentials(
        service=service,
        username=creds["username"],
        password=creds["password"]
    )
    print(f"✓ Migrated {service}")

# Delete old plaintext file
import os
os.remove("old_credentials.json")
print("✓ Migration complete")
```

## Testing

The credentials manager is tested in `tests/test_credentials_manager.py`:
- Encryption and decryption
- Key generation and persistence
- Multi-service support
- File permissions
- Backward compatibility
- Error handling
- Special characters in credentials

## Troubleshooting

### "Invalid token" or decryption errors

**Cause**: Encryption key changed or file corrupted  
**Solution**: Clear credentials and re-enter:
```bash
rm ~/.movie_sync/filelist_credentials.enc
# Re-run application to re-enter credentials
```

### "Permission denied"

**Cause**: File permissions too restrictive or directory not writable  
**Solution**: Check permissions:
```bash
ls -la ~/.movie_sync
chmod 700 ~/.movie_sync
chmod 600 ~/.movie_sync/.key
```

### Credentials not persisting

**Cause**: Directory creation failed or disk full  
**Solution**: Verify directory exists and is writable:
```bash
mkdir -p ~/.movie_sync
touch ~/.movie_sync/test
rm ~/.movie_sync/test
```
