"""
qBittorrent Manager
Handles adding torrents to qBittorrent and managing downloads
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Optional
from credentials_manager import CredentialsManager

try:
    import qbittorrentapi
except ImportError:
    qbittorrentapi = None


class QBittorrentManager:
    """Manage qBittorrent downloads"""
    
    def __init__(self, host: str = "localhost", port: int = 8080, 
                 username: str = "", password: str = "",
                 use_stored_credentials: bool = True):
        """
        Initialize qBittorrent manager
        
        Args:
            host: qBittorrent Web UI host (default: localhost)
            port: qBittorrent Web UI port (default: 8080)
            username: Web UI username (empty if no auth, or will prompt if use_stored_credentials=True)
            password: Web UI password (empty if no auth, or will prompt if use_stored_credentials=True)
            use_stored_credentials: Load credentials from encrypted storage if available
        """
        if qbittorrentapi is None:
            print("⚠ qbittorrent-api not installed. Install with: pip install qbittorrent-api")
            self.client = None
            return
        
        self.host = host
        self.port = port
        self.credentials_manager = CredentialsManager() if use_stored_credentials else None
        self.use_stored_credentials = use_stored_credentials
        self.client = None
        self.connection_failed = False
        
        # Load credentials from storage or use provided ones
        if use_stored_credentials and (not username or not password):
            stored_user, stored_pass = self._get_credentials()
            self.username = username or stored_user or ""
            self.password = password or stored_pass or ""
        else:
            self.username = username
            self.password = password
    
    def _get_credentials(self) -> tuple:
        """Get qBittorrent credentials from encrypted storage or prompt user"""
        if not self.credentials_manager:
            return "", ""
        
        # Try to load from storage
        username, password = self.credentials_manager.get_qbittorrent_credentials()
        
        if username and password:
            return username, password
        
        # If not found, prompt user
        print("\n=== qBittorrent Web UI Credentials ===")
        print("If your qBittorrent Web UI requires authentication, enter credentials.")
        print("Otherwise, just press Enter to skip (leave empty).")
        print()
        
        username = input("qBittorrent username (or press Enter): ").strip()
        password = input("qBittorrent password (or press Enter): ").strip()
        
        # Save if provided
        if username or password:
            self.credentials_manager.save_qbittorrent_credentials(username, password)
            print()
        
        return username, password
    
    def _ensure_qbittorrent_running(self) -> bool:
        """Check if qBittorrent is running, start it if not"""
        # Try to connect first
        if self._connect():
            return True
        
        print("  qBittorrent not running, attempting to start...")
        
        # Try to start qBittorrent
        try:
            # Try GUI version first
            subprocess.Popen(
                ['qbittorrent'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            print("  Started qBittorrent GUI...")
            
            # Wait a bit for it to start
            for i in range(10):
                time.sleep(1)
                if self._connect():
                    print("  ✓ Connected to qBittorrent")
                    return True
            
            print("  ⚠ qBittorrent started but Web UI not accessible")
            print("    Please enable Web UI in qBittorrent settings:")
            print("    Tools → Options → Web UI → Enable Web User Interface")
            return False
            
        except FileNotFoundError:
            # Try headless version
            try:
                subprocess.Popen(
                    ['qbittorrent-nox'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print("  Started qBittorrent headless...")
                
                # Wait for it to start
                for i in range(10):
                    time.sleep(1)
                    if self._connect():
                        print("  ✓ Connected to qBittorrent")
                        return True
                        
            except FileNotFoundError:
                print("  ✗ qBittorrent not found in PATH")
                print("    Please install qBittorrent or start it manually")
                return False
        
        return False
    
    def _connect(self) -> bool:
        """Connect to qBittorrent Web UI"""
        if self.client:
            try:
                # Test if connection is still alive
                self.client.app.version
                return True
            except:
                self.client = None
        
        if qbittorrentapi is None:
            return False
        
        try:
            self.client = qbittorrentapi.Client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
            # Test connection
            self.client.app.version
            self.connection_failed = False
            return True
        except qbittorrentapi.LoginFailed:
            if not self.connection_failed:
                print("  ✗ qBittorrent login failed - check username/password")
                self.connection_failed = True
            return False
        except Exception as e:
            # Connection failed (qBittorrent probably not running)
            return False
    
    def add_torrent(self, torrent_path: str, save_path: Optional[str] = None,
                   category: str = "Movies", tags: str = "movie_sync") -> bool:
        """
        Add a torrent file to qBittorrent
        
        Args:
            torrent_path: Path to the .torrent file
            save_path: Where to save downloaded files (None = default)
            category: Category for the torrent
            tags: Tags for the torrent
            
        Returns:
            True if torrent was added successfully
        """
        if qbittorrentapi is None:
            print("  ✗ qbittorrent-api not available")
            return False
        
        # Ensure qBittorrent is running and connected
        if not self._ensure_qbittorrent_running():
            print("  ✗ Could not connect to qBittorrent")
            return False
        
        try:
            # Verify torrent file exists
            torrent_path = Path(torrent_path)
            if not torrent_path.exists():
                print(f"  ✗ Torrent file not found: {torrent_path}")
                return False
            
            # Create category if it doesn't exist
            try:
                categories = self.client.torrents_categories()
                if category not in categories:
                    self.client.torrents_create_category(category)
            except:
                pass  # Category operations not critical
            
            # Add the torrent
            with open(torrent_path, 'rb') as f:
                torrent_file = f.read()
            
            result = self.client.torrents_add(
                torrent_files=torrent_file,
                save_path=save_path,
                category=category,
                tags=tags,
                is_paused=False
            )
            
            if result == "Ok.":
                print(f"  ✓ Added to qBittorrent (Category: {category})")
                return True
            else:
                print(f"  ⚠ qBittorrent response: {result}")
                return True  # Still consider it success
                
        except qbittorrentapi.Conflict409Error:
            print("  ℹ Torrent already exists in qBittorrent")
            return True  # Already exists is OK
        except Exception as e:
            print(f"  ✗ Failed to add torrent: {e}")
            return False
    
    def get_torrent_info(self, torrent_hash: str) -> Optional[dict]:
        """Get information about a torrent by its hash"""
        if not self.client:
            if not self._connect():
                return None
        
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if torrents:
                t = torrents[0]
                return {
                    "name": t.name,
                    "progress": t.progress,
                    "state": t.state,
                    "downloaded": t.downloaded,
                    "size": t.size,
                    "eta": t.eta,
                    "num_seeds": t.num_seeds
                }
        except:
            pass
        
        return None
    
    def list_torrents(self, category: str = None) -> list:
        """List all torrents, optionally filtered by category"""
        if not self.client:
            if not self._connect():
                return []
        
        try:
            torrents = self.client.torrents_info(category=category)
            return [
                {
                    "name": t.name,
                    "progress": t.progress * 100,
                    "state": t.state,
                    "category": t.category,
                    "size": t.size,
                    "eta": t.eta
                }
                for t in torrents
            ]
        except Exception as e:
            print(f"  ✗ Failed to list torrents: {e}")
            return []


if __name__ == "__main__":
    # Test qBittorrent connection
    print("qBittorrent Manager Test")
    print("=" * 60)
    
    manager = QBittorrentManager()
    
    if manager._ensure_qbittorrent_running():
        print("\n✓ qBittorrent is running and accessible")
        
        # List current torrents
        torrents = manager.list_torrents()
        print(f"\nCurrent torrents: {len(torrents)}")
        for i, t in enumerate(torrents[:5], 1):
            print(f"{i}. {t['name'][:50]}")
            print(f"   Progress: {t['progress']:.1f}% | State: {t['state']}")
    else:
        print("\n✗ Could not connect to qBittorrent")
        print("\nPlease ensure:")
        print("  1. qBittorrent is installed")
        print("  2. Web UI is enabled (Tools → Options → Web UI)")
        print("  3. Web UI port is 8080 (default)")
