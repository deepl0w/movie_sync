# Test Suite Documentation

## Overview

This directory contains comprehensive unit and integration tests for the Movie Sync application. The test suite uses `pytest` with mocking capabilities to test all components without requiring external dependencies like FileList.io or qBittorrent.

## Test Statistics

- **Total Tests**: 97
- **Coverage**: 71%
- **Test Files**: 7

## Running Tests

### Run All Tests
```bash
python -m pytest tests/
```

### Run with Verbose Output
```bash
python -m pytest tests/ -v
```

### Run with Coverage Report
```bash
python -m pytest tests/ --cov=. --cov-report=html
# View report in htmlcov/index.html
```

### Run Specific Test File
```bash
python -m pytest tests/test_credentials_manager.py -v
```

### Run Specific Test
```bash
python -m pytest tests/test_credentials_manager.py::TestCredentialsManager::test_save_and_get_credentials -v
```

## Test Structure

### `conftest.py`
Contains shared pytest fixtures used across all test files:
- `temp_dir`: Temporary directory for test isolation
- `config_dir`: Temporary config directory
- `sample_movie`: Sample movie data
- `sample_watchlist`: Sample watchlist data
- `sample_torrent_result`: Sample FileList.io torrent result
- `sample_filelist_config`: Sample configuration
- `mock_qbt_client`: Mock qBittorrent client
- `json_file_helper`: Helper to create JSON files

### `test_config.py` (6 tests)
Tests for configuration management:
- Loading default configuration
- Loading from file
- Saving configuration
- Error handling
- Config merging with defaults

### `test_credentials_manager.py` (15 tests)
Tests for encrypted credential storage:
- Initialization and directory creation
- Encryption key persistence
- Save/get credentials for multiple services
- Encryption verification
- Backward compatibility
- File permissions (600)
- Error handling for corrupted files
- Special characters in credentials

### `test_download_service.py` (10 tests)
Tests for the base download service:
- Initialization
- Queue loading and saving
- Adding movies to queue
- Processing downloads
- File operations
- Error handling

### `test_filelist_downloader.py` (19 tests)
Tests for FileList.io integration:
- Configuration loading
- Credential management
- API search (by IMDB and title)
- Quality selection algorithm
- Torrent selection preferences (quality, freeleech, seeders)
- Torrent file download
- qBittorrent integration
- Error handling (rate limits, invalid credentials)

### `test_monitor.py` (14 tests)
Tests for Letterboxd scraping:
- Watchlist fetching
- Pagination handling
- Movie details extraction (director, IMDB ID)
- Watchlist persistence
- Finding new movies
- Error handling
- Performance optimization (reusing cached data)

### `test_qbittorrent_manager.py` (20 tests)
Tests for qBittorrent integration:
- Initialization with/without API
- Credential storage
- Connection management
- Auto-starting qBittorrent
- Adding torrents
- Category creation
- Torrent info retrieval
- Error handling (login failures, connection errors)

### `test_main.py` (13 tests)
Integration tests for the main application:
- App initialization
- Title normalization
- Fuzzy matching for downloaded movies
- Queue management
- Dry-run mode
- Full workflow testing

## Mocking Strategy

### External Services
All external dependencies are mocked to ensure tests:
1. Run quickly
2. Don't require internet connection
3. Don't consume API rate limits
4. Are deterministic and reliable

**Mocked Components:**
- **FileList.io API**: Using `responses` library to mock HTTP requests
- **Letterboxd HTML**: Using `responses` library to mock HTML responses
- **qBittorrent API**: Using `pytest-mock` to mock the qbittorrentapi library
- **File System**: Using temporary directories (`temp_dir` fixture)
- **User Input**: Mocking `builtins.input` for credential prompts

### Key Mocking Patterns

```python
# Mock HTTP responses (FileList.io, Letterboxd)
@responses.activate
def test_search_movie(self):
    responses.add(
        responses.GET,
        "https://filelist.io/api.php",
        json=[{"name": "Movie", "seeders": 42}],
        status=200
    )
    # Test code here

# Mock qBittorrent client
def test_add_torrent(self, mocker, mock_qbt_client):
    mock_qbt_api = mocker.patch('qbittorrent_manager.qbittorrentapi')
    mock_qbt_api.Client.return_value = mock_qbt_client
    # Test code here

# Mock credentials manager
def test_with_credentials(self, mocker):
    mock_creds = mocker.patch('module.CredentialsManager')
    mock_instance = mock_creds.return_value
    mock_instance.get_credentials.return_value = ("user", "pass")
    # Test code here
```

## Coverage Goals

| Module | Coverage | Notes |
|--------|----------|-------|
| `config.py` | 100% | ✅ Full coverage |
| `credentials_manager.py` | 99% | ✅ Nearly complete |
| `download_service.py` | 95% | ✅ Excellent coverage |
| `monitor.py` | 94% | ✅ Excellent coverage |
| `qbittorrent_manager.py` | 78% | ⚠️ Some edge cases not covered |
| `filelist_downloader.py` | 76% | ⚠️ Some error paths not tested |
| `main.py` | 64% | ⚠️ CLI and continuous mode not fully tested |

## Adding New Tests

### Basic Test Template
```python
def test_feature_name(self, temp_dir, mocker):
    """Test description"""
    # Arrange: Set up test data and mocks
    # Act: Call the function being tested
    # Assert: Verify the results
    assert result == expected
```

### Test with Mocked HTTP
```python
@responses.activate
def test_api_call(self, temp_dir):
    """Test API interaction"""
    responses.add(
        responses.GET,
        "https://api.example.com/endpoint",
        json={"data": "value"},
        status=200
    )
    # Your test code
```

### Test with Temporary Files
```python
def test_file_operations(self, temp_dir, json_file_helper):
    """Test file handling"""
    # Create test file
    test_file = json_file_helper("test.json", {"key": "value"})
    
    # Your test code
    assert test_file.exists()
```

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest tests/ --cov=. --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Best Practices

1. **Isolation**: Each test is independent and uses temporary directories
2. **Descriptive Names**: Test names clearly describe what they test
3. **Arrange-Act-Assert**: Tests follow the AAA pattern
4. **Mocking**: External dependencies are always mocked
5. **Coverage**: Aim for >80% coverage on critical modules
6. **Fast**: Full suite runs in ~11 seconds
7. **Deterministic**: Tests produce same results every time

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the project root
cd /path/to/movie_sync
python -m pytest tests/
```

### Coverage Not Generated
```bash
# Install pytest-cov
pip install pytest-cov

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### Specific Test Failing
```bash
# Run with full traceback
pytest tests/test_file.py::test_name -vv --tb=long
```

## Future Improvements

- [ ] Increase coverage for `main.py` (CLI and continuous mode)
- [ ] Add performance/load tests
- [ ] Add end-to-end integration tests with Docker
- [ ] Test error recovery scenarios
- [ ] Add tests for concurrent operations
- [ ] Property-based testing with Hypothesis
