# Letterboxd Watchlist Monitor

## Overview

The `LetterboxdWatchlistMonitor` class scrapes and tracks a Letterboxd user's watchlist. It fetches movie data from Letterboxd.com and identifies new additions to the watchlist.

## Features

- **Web scraping**: Fetches watchlist via HTTP requests (no API key needed)
- **Pagination support**: Automatically handles multi-page watchlists
- **Movie metadata**: Extracts title, year, director, IMDB ID, and Letterboxd slug
- **Change detection**: Identifies new movies by comparing with saved watchlist
- **Caching**: Saves watchlist to avoid redundant director lookups
- **Robust parsing**: Handles various Letterboxd page formats

## API Reference

### Initialization

```python
from monitor import LetterboxdWatchlistMonitor

# Use default watchlist file location
monitor = LetterboxdWatchlistMonitor(username="deeplow")

# Use custom watchlist file
monitor = LetterboxdWatchlistMonitor(
    username="deeplow",
    watchlist_file="/path/to/watchlist.json"
)
```

**Parameters**:
- `username` (str): Letterboxd username
- `watchlist_file` (str, optional): Path to save watchlist cache. Defaults to `~/.movie_sync/watchlist.json`

### get_watchlist(fetch_directors=True)

Fetch the current watchlist from Letterboxd.

```python
movies = monitor.get_watchlist()
print(f"Found {len(movies)} movies")

for movie in movies[:3]:
    print(f"- {movie['title']} ({movie['year']}) dir. {movie.get('director', 'Unknown')}")
```

**Parameters**:
- `fetch_directors` (bool): Whether to fetch director information. Default: `True`
  - `True`: Fetches director for new movies (slower, complete metadata)
  - `False`: Skip director lookup (faster, minimal metadata)

**Returns**: `List[Dict]` - List of movie dictionaries

**Movie dictionary structure**:
```python
{
    "id": "12345",                                    # Letterboxd movie ID
    "title": "The Matrix (1999)",                     # Title with year
    "slug": "the-matrix",                             # URL slug
    "url": "https://letterboxd.com/film/the-matrix/", # Movie page URL
    "year": "1999",                                   # Release year
    "director": "The Wachowskis",                     # Director name (if fetched)
    "imdb_id": "tt0133093"                            # IMDB ID (if found)
}
```

### save_watchlist(movies)

Save watchlist to cache file.

```python
movies = monitor.get_watchlist()
monitor.save_watchlist(movies)
```

**Parameters**:
- `movies` (List[Dict]): List of movie dictionaries to save

**Behavior**:
- Creates directory if it doesn't exist
- Writes to JSON file with 2-space indentation
- Overwrites existing file

### load_saved_watchlist()

Load previously saved watchlist from cache.

```python
saved_movies = monitor.load_saved_watchlist()
print(f"Loaded {len(saved_movies)} cached movies")
```

**Returns**: `List[Dict]`
- List of movie dictionaries from cache
- Empty list `[]` if file doesn't exist or is invalid

### find_new_movies(current, previous)

Identify movies that are new (not in previous watchlist).

```python
current_movies = monitor.get_watchlist()
previous_movies = monitor.load_saved_watchlist()

new_movies = monitor.find_new_movies(current_movies, previous_movies)
print(f"{len(new_movies)} new movies added to watchlist")
```

**Parameters**:
- `current` (List[Dict]): Current watchlist
- `previous` (List[Dict]): Previous watchlist

**Returns**: `List[Dict]` - Movies in `current` but not in `previous`

**Comparison**: Uses movie `id` field to identify duplicates

### get_movie_details(slug)

Fetch detailed information for a specific movie.

```python
details = monitor.get_movie_details("the-matrix")
print(f"Director: {details.get('director')}")
print(f"IMDB: {details.get('imdb_id')}")
```

**Parameters**:
- `slug` (str): Letterboxd movie slug (from URL)

**Returns**: `Dict` with fields:
- `director` (str): Director name
- `imdb_id` (str): IMDB ID (if found)

**Error handling**:
- Returns `{}` on network errors
- Returns `{}` if movie page not found

## Usage Examples

### Basic Watchlist Monitoring

```python
from monitor import LetterboxdWatchlistMonitor

monitor = LetterboxdWatchlistMonitor(username="deeplow")

# Fetch current watchlist
current = monitor.get_watchlist()
print(f"📺 Found {len(current)} movies in watchlist")

# Load previous watchlist
previous = monitor.load_saved_watchlist()

# Find new additions
new_movies = monitor.find_new_movies(current, previous)
if new_movies:
    print(f"\n🆕 {len(new_movies)} new movies:")
    for movie in new_movies:
        print(f"  • {movie['title']} dir. {movie.get('director', 'Unknown')}")
else:
    print("\n No new movies")

# Save updated watchlist
monitor.save_watchlist(current)
```

### Continuous Monitoring

```python
from monitor import LetterboxdWatchlistMonitor
import time

monitor = LetterboxdWatchlistMonitor(username="deeplow")

while True:
    print("\n🔍 Checking watchlist...")
    
    current = monitor.get_watchlist()
    previous = monitor.load_saved_watchlist()
    new_movies = monitor.find_new_movies(current, previous)
    
    if new_movies:
        print(f"🆕 Found {len(new_movies)} new movies!")
        for movie in new_movies:
            print(f"  Adding: {movie['title']}")
            # Process new movie...
    else:
        print("✓ No new movies")
    
    monitor.save_watchlist(current)
    
    # Wait 1 hour
    print("⏰ Next check in 3600 seconds")
    time.sleep(3600)
```

### Fast Monitoring (Skip Directors)

```python
from monitor import LetterboxdWatchlistMonitor

monitor = LetterboxdWatchlistMonitor(username="deeplow")

# Fast fetch without director info
movies = monitor.get_watchlist(fetch_directors=False)

# Director info can be fetched later if needed
for movie in movies:
    if not movie.get('director'):
        details = monitor.get_movie_details(movie['slug'])
        movie.update(details)
```

### Extract Year from Title

```python
from monitor import LetterboxdWatchlistMonitor

monitor = LetterboxdWatchlistMonitor(username="deeplow")

# Helper method to extract year
year = monitor._extract_year_from_title("The Matrix (1999)")
print(year)  # Output: "1999"

# Works with various formats
print(monitor._extract_year_from_title("Movie Title (2020)"))  # "2020"
print(monitor._extract_year_from_title("No Year"))             # None
```

## Watchlist Cache

### File Format

**Location**: `~/.movie_sync/watchlist.json`

```json
[
  {
    "id": "3FLQ",
    "title": "The Matrix (1999)",
    "slug": "the-matrix",
    "url": "https://letterboxd.com/film/the-matrix/",
    "year": "1999",
    "director": "The Wachowskis",
    "imdb_id": "tt0133093"
  },
  {
    "id": "2b5E",
    "title": "Inception (2010)",
    "slug": "inception",
    "url": "https://letterboxd.com/film/inception/",
    "year": "2010",
    "director": "Christopher Nolan",
    "imdb_id": "tt1375666"
  }
]
```

### Cache Benefits

1. **Faster subsequent runs**: Avoid re-fetching director info for existing movies
2. **Change detection**: Identify new movies by comparing with cache
3. **Offline reference**: View watchlist even when Letterboxd is down
4. **Reduced API calls**: Minimize HTTP requests to Letterboxd

## Web Scraping Details

### Pagination

Letterboxd paginates watchlists with 28 movies per page:

```
Page 1: https://letterboxd.com/username/watchlist/
Page 2: https://letterboxd.com/username/watchlist/page/2/
Page 3: https://letterboxd.com/username/watchlist/page/3/
...
```

The monitor automatically fetches all pages until no more movies are found.

### HTML Parsing

Uses BeautifulSoup4 to parse Letterboxd's HTML:

1. **Movie list**: Finds `<li class="poster-container">` elements
2. **Movie ID**: Extracted from `data-film-id` attribute
3. **Slug**: Extracted from `data-film-slug` or `data-target-link`
4. **Title**: Extracted from `img` alt text
5. **Director**: Fetched from individual movie page (`p.text-link`)
6. **IMDB ID**: Extracted from movie page IMDB link

### Rate Limiting

**Considerations**:
- Letterboxd doesn't have official API rate limits (for scraping)
- Be respectful: Don't check too frequently (recommended: 5-60 minutes)
- User-Agent header is set to look like a browser
- Implements polite scraping with reasonable delays

**Best practices**:
```python
# Good: Check every hour
monitor = LetterboxdWatchlistMonitor(username="deeplow")
# In continuous mode: check_interval=3600

# Bad: Check every second
# This would be abusive and could get your IP blocked
```

## Error Handling

### Network Errors

```python
try:
    movies = monitor.get_watchlist()
except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
    # Use cached watchlist as fallback
    movies = monitor.load_saved_watchlist()
```

### Invalid Username

```python
movies = monitor.get_watchlist()
if not movies:
    print("Warning: Empty watchlist or invalid username")
```

### Corrupted Cache

```python
movies = monitor.load_saved_watchlist()
# Returns empty list [] if file is corrupted or missing
if not movies:
    print("Cache empty or invalid, fetching fresh...")
    movies = monitor.get_watchlist()
```

## Privacy Considerations

### Public Watchlists Only

- The monitor can only access **public** Letterboxd watchlists
- Private watchlists return empty results
- No authentication is performed (no Letterboxd API key needed)

### Make Your Watchlist Public

1. Go to https://letterboxd.com/settings/privacy/
2. Under "Watchlist Privacy", select "Anyone"
3. Save changes

## Performance

### Fetch Times

Typical performance with good network connection:

| Operation | Time | Notes |
|-----------|------|-------|
| Get watchlist (28 movies, no directors) | ~1s | Just scrape list page |
| Get watchlist (28 movies, with directors) | ~30s | Fetch each movie page |
| Get watchlist (100 movies, with directors) | ~2min | Multiple pages + director lookups |
| Load cached watchlist | <0.1s | Read JSON file |
| Save watchlist | <0.1s | Write JSON file |

### Optimization Tips

1. **Use cached director info**: Set `fetch_directors=False` and only fetch for new movies
2. **Adjust check interval**: Don't check more than once per 5 minutes
3. **Handle pagination**: Large watchlists (>100 movies) take longer

```python
# Optimized approach
current = monitor.get_watchlist(fetch_directors=False)
previous = monitor.load_saved_watchlist()
new = monitor.find_new_movies(current, previous)

# Only fetch directors for new movies
for movie in new:
    details = monitor.get_movie_details(movie['slug'])
    movie.update(details)
```

## Testing

The monitor is tested in `tests/test_monitor.py`:
- Watchlist scraping with mocked responses
- Pagination handling
- Director fetching
- IMDB ID extraction
- Cache save/load
- New movie detection
- Error handling

## Troubleshooting

### Empty watchlist returned

**Causes**:
- Username is incorrect
- Watchlist is private
- Network issues
- Letterboxd page structure changed

**Solutions**:
```python
# Verify username
print(f"Checking https://letterboxd.com/{username}/watchlist/")

# Check if public
# Visit the URL in a browser while logged out

# Enable debug output
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Missing director information

**Causes**:
- Movie page structure changed
- Director not listed on Letterboxd
- Network timeout

**Solutions**:
```python
# Manually check problematic movie
details = monitor.get_movie_details("problematic-slug")
print(details)

# Fall back to IMDB lookup if director is critical
```

### Slow performance

**Causes**:
- Large watchlist
- Fetching directors for many movies
- Slow network

**Solutions**:
- Use `fetch_directors=False`
- Implement incremental updates
- Cache aggressively
