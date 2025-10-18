"""
FileList.io Torrent Downloader
Downloads torrents from FileList.io using their official API
"""

import os
import json
import requests
from typing import Dict, Optional, List
from pathlib import Path
import time
from download_service import MovieDownloader
from credentials_manager import CredentialsManager
from qbittorrent_manager import QBittorrentManager


class FileListDownloader(MovieDownloader):
    """Download movies from FileList.io torrent tracker using official API"""
    
    def __init__(self, queue_file: Optional[str] = None, 
                 torrent_dir: Optional[str] = None,
                 config_file: Optional[str] = None,
                 use_qbittorrent: bool = True):
        # Use default paths in ~/.movie_sync if not specified
        config_dir = Path(os.path.expanduser("~/.movie_sync"))
        if queue_file is None:
            queue_file = str(config_dir / "download_queue.json")
        if config_file is None:
            config_file = str(config_dir / "filelist_config.json")
            
        super().__init__(queue_file)
        self.credentials_manager = CredentialsManager()
        self.session = requests.Session()
        
        # Set browser-like headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        
        self.base_url = "https://filelist.io"
        self.api_url = f"{self.base_url}/api.php"
        self.username = None
        self.passkey = None
        
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Build category list from config (ordered by priority)
        self.category_priority = {
            cat["id"]: cat["priority"] 
            for cat in self.config.get("category_priority", [])
        }
        self.movie_categories = [cat["id"] for cat in self.config.get("category_priority", [])]
        
        # Download preferences
        prefs = self.config.get("download_preferences", {})
        self.prefer_freeleech = prefs.get("prefer_freeleech", True)
        self.prefer_doubleup = prefs.get("prefer_doubleup", False)
        self.minimum_seeders = prefs.get("minimum_seeders", 1)
        
        # qBittorrent configuration
        qbt_config = self.config.get("qbittorrent", {})
        if use_qbittorrent and qbt_config.get("enabled", True):
            self.use_qbittorrent = True
            self.qbt_manager = QBittorrentManager(
                host=qbt_config.get("host", "localhost"),
                port=qbt_config.get("port", 8080),
                use_stored_credentials=True  # Always use encrypted credentials
            )
            self.qbt_category = qbt_config.get("category", "Movies")
            self.qbt_tags = qbt_config.get("tags", "movie_sync,filelist")
            self.qbt_save_path = qbt_config.get("save_path", None)
        else:
            self.use_qbittorrent = False
            self.qbt_manager = None
        
        # Set default torrent directory
        if torrent_dir is None:
            torrent_dir = os.path.expanduser("~/Downloads")
        self.torrent_dir = Path(torrent_dir)
        self.torrent_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_file: str) -> Dict:
        """Load FileList configuration from JSON file"""
        try:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                print(f"⚠ Config file not found: {config_file}, using defaults")
                return self._get_default_config()
        except Exception as e:
            print(f"⚠ Error loading config: {e}, using defaults")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration if config file is missing"""
        return {
            "category_priority": [
                {"id": 6, "name": "Filme 4K", "priority": 1},
                {"id": 4, "name": "Filme HD", "priority": 2},
                {"id": 19, "name": "Filme HD-RO", "priority": 3},
                {"id": 1, "name": "Filme SD", "priority": 4}
            ],
            "download_preferences": {
                "prefer_freeleech": True,
                "prefer_doubleup": False,
                "minimum_seeders": 1
            }
        }
    
    def _get_credentials(self) -> bool:
        """Get FileList.io API credentials (username + passkey)"""
        if self.username and self.passkey:
            return True
            
        # Get credentials from storage
        username, passkey = self.credentials_manager.get_filelist_credentials()
        if not username or not passkey:
            print("\n=== FileList.io API Credentials Required ===")
            print("You need your username and passkey (not password!) from FileList.io")
            print("To get your passkey:")
            print("  1. Log in to https://filelist.io")
            print("  2. Go to your profile settings")
            print("  3. Copy your API passkey")
            print()
            username = input("Username: ").strip()
            passkey = input("Passkey: ").strip()
            
            if not username or not passkey:
                print("Error: Username and passkey are required.")
                return False
            
            # Save credentials
            self.credentials_manager.save_filelist_credentials(username, passkey)
            print("Credentials saved securely.\n")
        
        self.username = username
        self.passkey = passkey
        return True
    
    def _search_movie(self, movie: Dict) -> List[Dict]:
        """Search for a movie on FileList.io using the official API
        
        Returns:
            List of torrent results with keys: name, size, seeders, download_link, id
        """
        if not self._get_credentials():
            return []
        
        try:
            # Prepare API parameters
            params = {
                "username": self.username,
                "passkey": self.passkey,
                "action": "search-torrents",
                "type": "imdb" if movie.get("imdb_id") else "name",
                "category": ",".join(map(str, self.movie_categories)),  # HD, 4K, Blu-Ray
            }
            
            # Add query parameter
            if movie.get("imdb_id"):
                # Clean IMDB ID (accept both tt1234567 and 1234567 formats)
                imdb_id = movie["imdb_id"].replace("tt", "")
                params["query"] = imdb_id
                print(f"  Searching FileList.io API for IMDB: tt{imdb_id}")
            else:
                # Fallback to title search
                title = movie.get("title", "")
                # Remove year from title if present
                if "(" in title and ")" in title:
                    title = title.split("(")[0].strip()
                params["query"] = title
                print(f"  Searching FileList.io API for: {title}")
            
            # Make API request
            response = self.session.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Handle API errors
            if isinstance(data, dict) and "error" in data:
                error_code = data.get("error")
                error_msg = data.get("message", "Unknown error")
                
                if error_code == 429:
                    print("  ✗ Rate limit reached (150 calls/hour). Please wait before trying again.")
                elif error_code == 403:
                    if "maxim" in error_msg.lower() or "depasit" in error_msg.lower():
                        print("  ✗ Too many failed authentications. Please wait an hour.")
                    else:
                        print(f"  ✗ Invalid credentials: {error_msg}")
                        self.credentials_manager.clear_filelist_credentials()
                elif error_code == 400:
                    print(f"  ✗ Invalid search parameters: {error_msg}")
                else:
                    print(f"  ✗ API Error {error_code}: {error_msg}")
                
                return []
            
            # Parse results
            results = []
            if isinstance(data, list):
                for item in data[:10]:  # Limit to top 10 results
                    try:
                        results.append({
                            "name": item.get("name", "Unknown"),
                            "size": item.get("size", "Unknown"),
                            "seeders": int(item.get("seeders", 0)),
                            "leechers": int(item.get("leechers", 0)),
                            "download_link": item.get("download_link", ""),
                            "id": item.get("id"),
                            "category": item.get("category"),
                            "freeleech": item.get("freeleech", 0),
                            "doubleup": item.get("doubleup", 0),
                        })
                    except Exception as e:
                        # Skip problematic items
                        continue
            
            print(f"  Found {len(results)} torrent(s)")
            return results
            
        except requests.exceptions.Timeout:
            print("  ✗ Request timed out")
            return []
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Network error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"  ✗ Failed to parse API response: {e}")
            return []
        except Exception as e:
            print(f"  ✗ Search error: {e}")
            return []
    
    def _download_torrent_file(self, torrent_id: str, movie_title: str) -> Optional[str]:
        """Download a .torrent file from FileList.io using the API
        
        Args:
            torrent_id: The FileList.io torrent ID
            movie_title: Title of the movie (for filename)
            
        Returns:
            Path to downloaded .torrent file, or None if failed
        """
        if not self._get_credentials():
            return None
        
        try:
            # Build download URL with authentication
            download_url = f"https://filelist.io/download.php"
            params = {
                "id": torrent_id,
                "username": self.username,
                "passkey": self.passkey
            }
            
            print(f"  Downloading torrent file for: {movie_title}")
            
            # Download the .torrent file
            response = self.session.get(download_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Check if we got a valid torrent file
            content_type = response.headers.get("Content-Type", "")
            if "application/x-bittorrent" not in content_type and not response.content.startswith(b"d8:"):
                print(f"  ✗ Invalid response - not a torrent file (Content-Type: {content_type})")
                return None
            
            # Sanitize filename and save
            safe_filename = "".join(c for c in movie_title if c.isalnum() or c in (' ', '-', '_')).strip()
            torrent_path = self.torrent_dir / f"{safe_filename}_{torrent_id}.torrent"
            
            with open(torrent_path, "wb") as f:
                f.write(response.content)
            
            print(f"  ✓ Torrent saved to: {torrent_path}")
            return str(torrent_path)
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Download failed: {e}")
            return None
        except Exception as e:
            print(f"  ✗ Unexpected error downloading torrent: {e}")
            return None
    
    def _select_best_torrent(self, results: List[Dict]) -> Optional[Dict]:
        """Select the best torrent based on quality priority and seeders
        
        Strategy:
        1. Filter by minimum seeders
        2. Group by category priority (quality)
        3. Within highest quality tier, optionally prefer freeleech/doubleup
        4. Select torrent with most seeders
        
        Returns:
            Best torrent dict, or None if no suitable torrent found
        """
        if not results:
            return None
        
        # Filter by minimum seeders
        viable_torrents = [
            t for t in results 
            if t.get('seeders', 0) >= self.minimum_seeders
        ]
        
        if not viable_torrents:
            print(f"  ⚠ No torrents with >= {self.minimum_seeders} seeders, trying all results...")
            viable_torrents = results
        
        # Group torrents by category priority
        quality_groups = {}
        for torrent in viable_torrents:
            cat_id = torrent.get('category')
            priority = self.category_priority.get(cat_id, 999)  # Unknown categories get low priority
            
            if priority not in quality_groups:
                quality_groups[priority] = []
            quality_groups[priority].append(torrent)
        
        if not quality_groups:
            return None
        
        # Get the highest priority (lowest number) group
        best_priority = min(quality_groups.keys())
        best_quality_torrents = quality_groups[best_priority]
        
        # Get category name for logging
        cat_id = best_quality_torrents[0].get('category')
        cat_name = next(
            (c['name'] for c in self.config.get('category_priority', []) if c['id'] == cat_id),
            f"Category {cat_id}"
        )
        
        print(f"  → Filtering to '{cat_name}' quality tier ({len(best_quality_torrents)} torrent(s))")
        
        # Within best quality tier, apply preferences
        candidates = best_quality_torrents
        
        # Prefer freeleech if enabled
        if self.prefer_freeleech:
            freeleech_torrents = [t for t in candidates if t.get('freeleech')]
            if freeleech_torrents:
                print(f"  → Preferring freeleech torrents ({len(freeleech_torrents)} available)")
                candidates = freeleech_torrents
        
        # Prefer doubleup if enabled (and not already filtered to freeleech)
        if self.prefer_doubleup and not self.prefer_freeleech:
            doubleup_torrents = [t for t in candidates if t.get('doubleup')]
            if doubleup_torrents:
                print(f"  → Preferring double-up torrents ({len(doubleup_torrents)} available)")
                candidates = doubleup_torrents
        
        # Select torrent with most seeders
        best_torrent = max(candidates, key=lambda x: x.get('seeders', 0))
        
        return best_torrent
    
    def _find_existing_torrent(self, movie: Dict) -> Optional[Path]:
        """Find existing torrent file using fuzzy matching
        
        Args:
            movie: Movie dictionary with title and year
            
        Returns:
            Path to existing torrent file, or None if not found
        """
        if not self.torrent_dir.exists():
            return None
        
        from difflib import SequenceMatcher
        import re
        
        title = movie.get('title', '')
        year = movie.get('year', '')
        
        # Normalize title for matching
        normalized_title = title.lower().replace(' ', '.').replace(':', '').replace("'", '')
        
        # Search through torrent files
        best_match = None
        best_similarity = 0
        
        for torrent_file in self.torrent_dir.glob('*.torrent'):
            if not torrent_file.is_file():
                continue
            
            filename = torrent_file.stem.lower()
            
            # First check: if normalized title is in filename (fast and accurate)
            if normalized_title in filename:
                # If year is specified, verify it's also in the filename
                if year:
                    if str(year) in filename:
                        return torrent_file
                else:
                    # No year specified, title match is enough
                    return torrent_file
            
            # Second check: fuzzy matching on title portion only
            # Extract title portion (before quality indicators)
            title_part = re.split(r'\d{3,4}p|bluray|brrip|webrip|hdtv|dvdrip|x264|x265|h264|h265',
                                filename, flags=re.IGNORECASE)[0]
            
            # Calculate similarity
            similarity = SequenceMatcher(None, normalized_title, title_part).ratio()
            
            # Bonus for year match
            if year and str(year) in filename:
                similarity += 0.10
            
            # Lower threshold for fuzzy matching (75% instead of 85%)
            if similarity >= 0.75 and similarity > best_similarity:
                best_similarity = similarity
                best_match = torrent_file
        
        return best_match
    
    def download_movie(self, movie: Dict) -> bool:
        """Download a movie from FileList.io
        
        Args:
            movie: Dictionary containing movie information (title, year, imdb_id, etc.)
            
        Returns:
            True if torrent was successfully downloaded, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Downloading: {movie['title']}")
        print(f"Director: {movie.get('director', 'Unknown')}")
        if movie.get('imdb_id'):
            print(f"IMDB: https://www.imdb.com/title/{movie['imdb_id']}/")
        print(f"{'='*60}")
        
        # Check if torrent file already exists locally (using fuzzy matching)
        existing_torrent = self._find_existing_torrent(movie)
        
        if existing_torrent:
            print(f"  ℹ Torrent file already exists: {existing_torrent}")
            
            # Try to add to qBittorrent if enabled
            if self.use_qbittorrent and self.qbt_manager:
                print(f"  Checking if already in qBittorrent...")
                if self.qbt_manager.add_torrent(
                    torrent_path=str(existing_torrent),
                    save_path=self.qbt_save_path,
                    category=self.qbt_category,
                    tags=self.qbt_tags
                ):
                    print(f"  ✓ Torrent added to qBittorrent (or already exists)")
                else:
                    print(f"  ⚠ Could not add to qBittorrent")
                    return False
            
            return True
        
        # Search for the movie
        results = self._search_movie(movie)
        
        if not results:
            print("✗ No torrents found for this movie.")
            return False
        
        # Display results
        print(f"\nFound {len(results)} torrent(s):")
        for i, result in enumerate(results, 1):
            cat_id = result.get('category')
            cat_name = next(
                (c['name'] for c in self.config.get('category_priority', []) if c['id'] == cat_id),
                f"Cat{cat_id}"
            )
            priority = self.category_priority.get(cat_id, 999)
            freeleech = " [FREELEECH]" if result.get('freeleech') else ""
            doubleup = " [2x UPLOAD]" if result.get('doubleup') else ""
            print(f"{i}. [{cat_name}] {result['name']}{freeleech}{doubleup}")
            print(f"   Size: {result['size']} | Seeders: {result['seeders']} | Leechers: {result.get('leechers', 0)}")
        
        # Select best torrent based on quality priority
        best_torrent = self._select_best_torrent(results)
        
        if not best_torrent:
            print("✗ No suitable torrent found after filtering.")
            return False
        
        print(f"\n✓ Selected: {best_torrent['name']}")
        print(f"  Seeders: {best_torrent['seeders']} | Size: {best_torrent['size']}")
        
        # Download the torrent file
        if best_torrent['id']:
            torrent_path = self._download_torrent_file(best_torrent['id'], movie['title'])
            if torrent_path:
                print(f"✓ Successfully downloaded torrent for {movie['title']}")
                
                # Add to qBittorrent if enabled
                if self.use_qbittorrent and self.qbt_manager:
                    print(f"\n  Adding to qBittorrent...")
                    if self.qbt_manager.add_torrent(
                        torrent_path=torrent_path,
                        save_path=self.qbt_save_path,
                        category=self.qbt_category,
                        tags=self.qbt_tags
                    ):
                        print(f"  ✓ Torrent added to qBittorrent and download started")
                    else:
                        print(f"  ⚠ Could not add to qBittorrent (torrent file saved locally)")
                        return False
                
                return True
        
        print(f"✗ Failed to download torrent for {movie['title']}")
        return False
    
    def process_downloads(self) -> None:
        """Process the download queue"""
        pending = [m for m in self.queue if m["status"] == "pending"]
        if not pending:
            print("No pending downloads.")
            return
        
        print(f"\nProcessing {len(pending)} pending download(s)...")
        
        for movie in pending:
            success = self.download_movie(movie)
            
            if success:
                movie["status"] = "downloaded"
                movie["downloaded_at"] = int(time.time())
            else:
                movie["status"] = "failed"
                movie["failed_at"] = int(time.time())
            
            self._save_queue()
            
            # Rate limiting between downloads
            time.sleep(2)
        
        print("\n✓ Download queue processed.")


if __name__ == "__main__":
    # Note: Avoid running tests directly - FileList.io has a 150 API calls/hour limit
    # Use main.py to process your download queue instead
    print("FileList.io Torrent Downloader")
    print("=" * 60)
    print("⚠ This module should be used via main.py, not run directly.")
    print("  FileList.io API has a limit of 150 calls per hour.")
    print("\nTo download movies:")
    print("  python main.py")
    print("\nConfiguration:")
    print("  Edit filelist_config.json to adjust quality priorities")
    print("=" * 60)
