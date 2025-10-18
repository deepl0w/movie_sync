import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

class LetterboxdWatchlistMonitor:
    """Monitor for Letterboxd watchlist - only fetches and tracks watchlist changes"""
    
    def __init__(self, username: str, watchlist_file: Optional[str] = None):
        """
        Initialize the Letterboxd watchlist monitor.
        
        Args:
            username: Letterboxd username
            watchlist_file: Path to store the watchlist data (defaults to ~/.movie_sync/watchlist.json)
        """
        self.username = username
        # Use default path in ~/.movie_sync if not specified
        if watchlist_file is None:
            config_dir = Path(os.path.expanduser("~/.movie_sync"))
            watchlist_file = str(config_dir / "watchlist.json")
        self.watchlist_file = watchlist_file
        
    def get_watchlist(self, fetch_directors: bool = True) -> List[Dict]:
        """Scrapes the user's Letterboxd watchlist with pagination support
        
        Args:
            fetch_directors: If True, fetch director info for each movie (slower but complete)
        """
        base_url = f"https://letterboxd.com/{self.username}/watchlist/"
        movies = []
        page = 1
        total_movies_found = 0
        
        # Load existing watchlist to preserve director info for unchanged movies
        saved_watchlist = self.load_saved_watchlist()
        saved_movies_dict = {movie["id"]: movie for movie in saved_watchlist}
        
        while True:
            try:
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                print(f"Fetching watchlist page {page}...")
            except:
                break
            
            try:
                response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, "html.parser")

                # Letterboxd uses React components with data-target-link attributes
                movie_items = soup.find_all('div', {'data-target-link': True})
                
                # If no movies found on this page, we've reached the end
                if not movie_items:
                    break
                
                print(f"Found {len(movie_items)} movies on page {page}")
                total_movies_found += len(movie_items)
                
                for item in movie_items:
                    film_id = item.get("data-film-id")
                    film_slug = item.get("data-item-slug")
                    title = item.get("data-item-name", "Unknown")
                    film_url = f"https://letterboxd.com{item.get('data-item-link', '')}"
                    
                    if film_id and film_slug:
                        # Extract year from title if it's in format "Title (Year)"
                        year = "Unknown"
                        if title and "(" in title and ")" in title:
                            year_match = re.search(r'\((\d{4})\)', title)
                            if year_match:
                                year = year_match.group(1)
                        
                        # Check if we already have this movie's info
                        if film_id in saved_movies_dict:
                            # Reuse existing movie info
                            director = saved_movies_dict[film_id].get("director", "Unknown")
                            imdb_id = saved_movies_dict[film_id].get("imdb_id")
                        elif fetch_directors:
                            # Fetch movie details from the film page (only for new movies)
                            print(f"  Fetching details for new movie: {title}")
                            director, imdb_id = self._get_movie_details(film_slug)
                            time.sleep(0.5)  # Small delay to avoid rate limiting
                        else:
                            director = "Unknown"
                            imdb_id = None
                        
                        movies.append({
                            "id": film_id,
                            "title": title,
                            "slug": film_slug,
                            "url": film_url,
                            "year": year,
                            "director": director,
                            "imdb_id": imdb_id,
                            "added_at": saved_movies_dict[film_id].get("added_at", int(time.time())) if film_id in saved_movies_dict else int(time.time())
                        })
                
                # Move to next page
                page += 1
                # Add a small delay to avoid hitting rate limits
                time.sleep(1)
                
            except Exception as e:
                print(f"Error fetching watchlist page {page}: {e}")
                break
        
        print(f"Total movies found across {page-1} pages: {total_movies_found}")
        return movies
    
    def _get_movie_details(self, film_slug: str) -> tuple[str, str]:
        """Fetch director and IMDB ID from the film page
        
        Returns:
            tuple: (director, imdb_id)
        """
        try:
            film_url = f"https://letterboxd.com/film/{film_slug}/"
            response = requests.get(film_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Get director
            director = "Unknown"
            director_meta = soup.find("meta", {"name": "twitter:data1"})
            if director_meta and director_meta.get("content"):
                director = director_meta.get("content", "Unknown")
            else:
                # Alternative: look for director link
                director_link = soup.select_one('a[href*="/director/"]')
                if director_link:
                    director = director_link.text.strip()
            
            # Get IMDB ID
            imdb_id = None
            # Look for IMDB link in the page
            imdb_link = soup.select_one('a[href*="imdb.com/title/"]')
            if imdb_link:
                imdb_url = imdb_link.get("href", "")
                # Extract ID from URL like https://www.imdb.com/title/tt0133093/
                if "/title/" in imdb_url:
                    imdb_id = imdb_url.split("/title/")[1].rstrip("/").split("/")[0]
            
            # Alternative: check data attributes
            if not imdb_id:
                imdb_data = soup.find(attrs={"data-imdb-id": True})
                if imdb_data:
                    imdb_id = imdb_data.get("data-imdb-id")
            
            return director, imdb_id
        except Exception as e:
            print(f"  Warning: Could not fetch details for {film_slug}: {e}")
            return "Unknown", None
    
    def load_saved_watchlist(self) -> List[Dict]:
        """Load the previously saved watchlist"""
        if not os.path.exists(self.watchlist_file):
            return []
        
        try:
            with open(self.watchlist_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading watchlist file: {e}")
            return []
    
    def save_watchlist(self, movies: List[Dict]) -> None:
        """Save the current watchlist to file"""
        with open(self.watchlist_file, 'w') as f:
            json.dump(movies, f, indent=2)
    
    def find_new_movies(self, current: List[Dict], previous: List[Dict]) -> List[Dict]:
        """Find new movies added to the watchlist"""
        previous_ids = {movie["id"] for movie in previous}
        return [movie for movie in current if movie["id"] not in previous_ids]

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    # Default watchlist file in ~/.movie_sync
    default_watchlist = str(Path(os.path.expanduser("~/.movie_sync")) / "watchlist.json")
    
    parser = argparse.ArgumentParser(description="Monitor a Letterboxd watchlist for changes")
    parser.add_argument("username", help="Letterboxd username")
    parser.add_argument("--file", default=default_watchlist, help="Watchlist storage file")
    
    args = parser.parse_args()
    
    monitor = LetterboxdWatchlistMonitor(
        username=args.username,
        watchlist_file=args.file
    )
    
    # Fetch and save watchlist
    print(f"Fetching watchlist for user: {args.username}")
    movies = monitor.get_watchlist()
    print(f"\nFound {len(movies)} movies")
    monitor.save_watchlist(movies)
    print(f"Saved to {args.file}")