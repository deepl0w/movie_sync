from typing import Dict, List, Optional
import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path

class MovieDownloader:
    """Interface for downloading movies from the watchlist."""
    
    def __init__(self, queue_file: Optional[str] = None):
        # Use default path in ~/.movie_sync if not specified
        if queue_file is None:
            config_dir = Path(os.path.expanduser("~/.movie_sync"))
            queue_file = str(config_dir / "download_queue.json")
        self.queue_file = queue_file
        self._load_queue()
    
    def _load_queue(self) -> None:
        """Load the download queue from file."""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r') as f:
                    self.queue = json.load(f)
            except Exception as e:
                print(f"Error loading download queue: {e}")
                self.queue = []
        else:
            self.queue = []
    
    def _save_queue(self) -> None:
        """Save the download queue to file."""
        with open(self.queue_file, 'w') as f:
            json.dump(self.queue, f, indent=2)
    
    def queue_movie(self, movie: Dict) -> None:
        """Add a movie to the download queue."""
        # Add to queue with status
        download_item = {
            **movie,
            "queued_at": int(time.time()),
            "status": "pending"
        }
        self.queue.append(download_item)
        self._save_queue()
        
        # Start the download process
        self.process_downloads()
    
    def process_downloads(self) -> None:
        """Process the download queue."""
        # This would typically be implemented with actual download logic
        # For now, we'll just log that downloads would occur
        pending = [m for m in self.queue if m["status"] == "pending"]
        if pending:
            print(f"Would download {len(pending)} movies:")
            for movie in pending:
                print(f"  - {movie['title']}")
                # Here you would call your actual downloader
                # self.download_movie(movie)
                
                # Mark as downloaded in the queue
                movie["status"] = "downloaded"
                movie["downloaded_at"] = int(time.time())
            
            self._save_queue()
    
    def download_movie(self, movie: Dict) -> bool:
        """
        Download a movie - to be implemented by user.
        
        This is a placeholder method that should be replaced with 
        actual download implementation.
        """
        # Implement your actual download logic here
        print(f"Downloading movie: {movie['title']}")
        
        # Simulate download success
        return True

# The user can extend this class with their actual download implementation
class CustomMovieDownloader(MovieDownloader):
    def download_movie(self, movie: Dict) -> bool:
        """Custom implementation of movie downloading."""
        # Example implementation
        print(f"Custom downloader searching for {movie['title']}")
        
        # Add your torrent/download implementation here
        # ...
        
        return True