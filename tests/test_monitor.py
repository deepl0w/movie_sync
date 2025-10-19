"""Tests for Letterboxd Monitor"""

import pytest
import responses
from unittest.mock import MagicMock, patch
import json

from monitor import LetterboxdWatchlistMonitor


class TestLetterboxdWatchlistMonitor:
    """Test cases for the LetterboxdWatchlistMonitor class"""
    
    def test_initialization(self, temp_dir):
        """Test monitor initialization"""
        watchlist_file = str(temp_dir / "watchlist.json")
        monitor = LetterboxdWatchlistMonitor("testuser", watchlist_file)
        
        assert monitor.username == "testuser"
        assert monitor.watchlist_file == watchlist_file
    
    @responses.activate
    def test_get_watchlist_single_page(self, temp_dir):
        """Test fetching watchlist with single page"""
        # Mock HTML response with movie items
        html_content = """
        <html>
            <div data-target-link="/film/the-matrix/" 
                 data-film-id="12345" 
                 data-item-slug="the-matrix"
                 data-item-name="The Matrix (1999)"
                 data-item-link="/film/the-matrix/"></div>
            <div data-target-link="/film/inception/" 
                 data-film-id="67890" 
                 data-item-slug="inception"
                 data-item-name="Inception (2010)"
                 data-item-link="/film/inception/"></div>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://letterboxd.com/testuser/watchlist/",
            body=html_content,
            status=200
        )
        
        # Mock empty response for page 2 (end of pagination)
        responses.add(
            responses.GET,
            "https://letterboxd.com/testuser/watchlist/page/2/",
            body="<html></html>",
            status=200
        )
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        movies = monitor.get_watchlist(fetch_directors=False)
        
        assert len(movies) == 2
        assert movies[0]["id"] == "12345"
        assert movies[0]["title"] == "The Matrix (1999)"
        assert movies[0]["slug"] == "the-matrix"
        assert movies[1]["id"] == "67890"
    
    @responses.activate
    def test_get_watchlist_multiple_pages(self, temp_dir):
        """Test fetching watchlist with pagination"""
        # Page 1
        page1_html = """
        <html>
            <div data-target-link="/film/movie1/" 
                 data-film-id="1" 
                 data-item-slug="movie1"
                 data-item-name="Movie 1"
                 data-item-link="/film/movie1/"></div>
        </html>
        """
        
        # Page 2
        page2_html = """
        <html>
            <div data-target-link="/film/movie2/" 
                 data-film-id="2" 
                 data-item-slug="movie2"
                 data-item-name="Movie 2"
                 data-item-link="/film/movie2/"></div>
        </html>
        """
        
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/", body=page1_html, status=200)
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/page/2/", body=page2_html, status=200)
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/page/3/", body="<html></html>", status=200)
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        movies = monitor.get_watchlist(fetch_directors=False)
        
        assert len(movies) == 2
        assert movies[0]["id"] == "1"
        assert movies[1]["id"] == "2"
    
    @responses.activate
    def test_get_movie_details(self, temp_dir):
        """Test fetching movie details from film page"""
        # Mock film page with director and IMDB link
        film_html = """
        <html>
            <meta name="twitter:data1" content="Christopher Nolan" />
            <a href="https://www.imdb.com/title/tt1375666/">IMDB</a>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://letterboxd.com/film/inception/",
            body=film_html,
            status=200
        )
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        director, imdb_id = monitor._get_movie_details("inception")
        
        assert director == "Christopher Nolan"
        assert imdb_id == "tt1375666"
    
    @responses.activate
    def test_get_movie_details_alternative_director(self, temp_dir):
        """Test fetching director from alternative HTML structure"""
        # Mock film page with director link (no meta tag)
        film_html = """
        <html>
            <a href="/director/steven-spielberg/">Steven Spielberg</a>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://letterboxd.com/film/jurassic-park/",
            body=film_html,
            status=200
        )
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        director, imdb_id = monitor._get_movie_details("jurassic-park")
        
        assert director == "Steven Spielberg"
    
    @responses.activate
    def test_get_movie_details_error_handling(self, temp_dir, caplog):
        """Test error handling when fetching movie details fails"""
        responses.add(
            responses.GET,
            "https://letterboxd.com/film/error-movie/",
            status=500
        )
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        director, imdb_id = monitor._get_movie_details("error-movie")
        
        assert director == "Unknown"
        assert imdb_id is None
        assert "warning" in caplog.text.lower() or "could not fetch" in caplog.text.lower()
    
    def test_save_and_load_watchlist(self, temp_dir, sample_watchlist):
        """Test saving and loading watchlist from file"""
        watchlist_file = temp_dir / "watchlist.json"
        monitor = LetterboxdWatchlistMonitor("testuser", str(watchlist_file))
        
        # Save watchlist
        monitor.save_watchlist(sample_watchlist)
        
        assert watchlist_file.exists()
        
        # Load watchlist
        loaded = monitor.load_saved_watchlist()
        
        assert len(loaded) == len(sample_watchlist)
        assert loaded[0]["id"] == sample_watchlist[0]["id"]
        assert loaded[0]["title"] == sample_watchlist[0]["title"]
    
    def test_load_nonexistent_watchlist(self, temp_dir):
        """Test loading watchlist when file doesn't exist"""
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "nonexistent.json"))
        
        loaded = monitor.load_saved_watchlist()
        
        assert loaded == []
    
    def test_load_corrupted_watchlist(self, temp_dir, caplog):
        """Test loading corrupted watchlist file"""
        watchlist_file = temp_dir / "corrupted.json"
        watchlist_file.write_text("invalid json {{{")
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(watchlist_file))
        loaded = monitor.load_saved_watchlist()
        
        assert loaded == []
        assert "error loading" in caplog.text.lower()
    
    def test_find_new_movies(self, temp_dir, sample_watchlist):
        """Test finding new movies added to watchlist"""
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        
        previous = [sample_watchlist[0]]  # Only first movie
        current = sample_watchlist  # Both movies
        
        new_movies = monitor.find_new_movies(current, previous)
        
        assert len(new_movies) == 1
        assert new_movies[0]["id"] == sample_watchlist[1]["id"]
    
    def test_find_new_movies_empty_previous(self, temp_dir, sample_watchlist):
        """Test finding new movies when previous watchlist is empty"""
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        
        new_movies = monitor.find_new_movies(sample_watchlist, [])
        
        assert len(new_movies) == len(sample_watchlist)
    
    def test_find_new_movies_no_new(self, temp_dir, sample_watchlist):
        """Test finding new movies when there are none"""
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        
        new_movies = monitor.find_new_movies(sample_watchlist, sample_watchlist)
        
        assert len(new_movies) == 0
    
    @responses.activate
    def test_extract_year_from_title(self, temp_dir):
        """Test extracting year from movie title"""
        html_content = """
        <html>
            <div data-target-link="/film/blade-runner/" 
                 data-film-id="123" 
                 data-item-slug="blade-runner"
                 data-item-name="Blade Runner (1982)"
                 data-item-link="/film/blade-runner/"></div>
        </html>
        """
        
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/", body=html_content, status=200)
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/page/2/", body="<html></html>", status=200)
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(temp_dir / "watchlist.json"))
        movies = monitor.get_watchlist(fetch_directors=False)
        
        assert movies[0]["year"] == "1982"
    
    @responses.activate
    def test_reuse_existing_movie_info(self, temp_dir, sample_movie):
        """Test that existing movie info is reused to avoid re-fetching"""
        # Save existing watchlist with director info
        watchlist_file = temp_dir / "watchlist.json"
        with open(watchlist_file, 'w') as f:
            json.dump([sample_movie], f)
        
        # Mock HTML with the same movie
        html_content = f"""
        <html>
            <div data-target-link="/film/{sample_movie['slug']}/" 
                 data-film-id="{sample_movie['id']}" 
                 data-item-slug="{sample_movie['slug']}"
                 data-item-name="{sample_movie['title']}"
                 data-item-link="/film/{sample_movie['slug']}/"></div>
        </html>
        """
        
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/", body=html_content, status=200)
        responses.add(responses.GET, "https://letterboxd.com/testuser/watchlist/page/2/", body="<html></html>", status=200)
        
        monitor = LetterboxdWatchlistMonitor("testuser", str(watchlist_file))
        movies = monitor.get_watchlist(fetch_directors=True)
        
        # Should reuse existing director info without fetching film page
        assert movies[0]["director"] == sample_movie["director"]
        assert movies[0]["imdb_id"] == sample_movie["imdb_id"]
        
        # Verify no film page was fetched (only watchlist pages)
        assert len(responses.calls) == 2
