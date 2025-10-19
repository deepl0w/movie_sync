#!/usr/bin/env python3
"""
Movie Sync - Letterboxd to FileList.io Integration

This application monitors your Letterboxd watchlist and automatically
downloads movies from FileList.io torrent tracker.

Architecture:
- Monitor thread: Periodically checks Letterboxd watchlist and adds new movies to queue
- Download thread: Processes download queue with automatic retries
- Queue system: Thread-safe pending/failed/completed queues with JSON persistence

Features:
- Automatic retry with exponential backoff
- Crash recovery via JSON checkpoints
- Graceful shutdown (Ctrl+C)
- Thread-safe queue operations
- No data loss on unexpected shutdown
"""

import argparse
import time
import os
import signal
import sys
import logging
from pathlib import Path

from config import Config
from queue_manager import QueueManager
from workers import MonitorWorker, DownloadWorker, CleanupWorker
from cleanup_service import CleanupService

# Module logger
logger = logging.getLogger(__name__)

try:
    from filelist_downloader import FileListDownloader
    FILELIST_AVAILABLE = True
except ImportError:
    FILELIST_AVAILABLE = False
    logger.error("FileList downloader not available - install required packages: pip install -r requirements.txt")


def setup_logging(log_file: str | None = None, console_level: str = "INFO"):
    """
    Set up logging configuration
    
    Args:
        log_file: Path to log file (default: ~/.movie_sync/movie_sync.log)
        console_level: Minimum log level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Default log file location
    if log_file is None:
        log_dir = Path(os.path.expanduser("~/.movie_sync"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "movie_sync.log"
    else:
        log_file_path = Path(log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert console_level string to logging level
    console_level_int = getattr(logging, console_level.upper(), logging.INFO)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # File handler - always logs everything at DEBUG level
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - respects console_level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level_int)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized - File: {log_file_path}, Console level: {logging.getLevelName(console_level_int)}")
    
    return str(log_file_path)


def run_movie_sync(config: dict):
    """
    Run Movie Sync in threaded mode
    
    Args:
        config: Configuration dictionary
    """
    logger.info("=" * 70)
    logger.info("MOVIE SYNC - Letterboxd to FileList.io")
    logger.info("=" * 70)
    logger.info(f"Letterboxd user: {config['username']}")
    logger.info(f"Monitor interval: {config['check_interval']}s ({config['check_interval']//60} minutes)")
    logger.info(f"Retry interval: {config.get('retry_interval', 3600)}s ({config.get('retry_interval', 3600)//60} minutes)")
    logger.info(f"Max retries: {config.get('max_retries', 5)}")
    logger.info(f"Download directory: {config.get('download_directory', '~/Downloads')}")
    
    # Cleanup configuration
    cleanup_enabled = config.get('enable_removal_cleanup', False)
    grace_period = config.get('removal_grace_period', 604800)
    grace_days = grace_period // 86400
    logger.info(f"Cleanup: {'ENABLED' if cleanup_enabled else 'DISABLED'} "
          f"(grace period: {grace_days} days)")
    
    logger.info("Press Ctrl+C to stop gracefully")
    logger.info("=" * 70)
    
    # Check dependencies
    if not FILELIST_AVAILABLE:
        logger.error("Cannot start: FileList downloader not available")
        return 1
    
    # Initialize queue manager
    logger.info("Initializing queue manager...")
    queue_manager = QueueManager()
    
    # Initialize downloader
    logger.info("Initializing FileList downloader...")
    downloader = FileListDownloader(
        queue_file=None,  # Not used in threaded mode
        use_qbittorrent=True
    )
    
    # Create worker threads
    logger.info("Creating monitor worker...")
    monitor_worker = MonitorWorker(
        username=config['username'],
        queue_manager=queue_manager,
        check_interval=config['check_interval'],
        watchlist_file=config.get('watchlist_file')
    )
    
    logger.info("Creating download worker...")
    download_worker = DownloadWorker(
        queue_manager=queue_manager,
        downloader=downloader,
        download_dir=config.get('download_directory', os.path.expanduser("~/Downloads")),
        retry_interval=config.get('retry_interval', 3600),
        max_retries=config.get('max_retries', 5),
        backoff_multiplier=config.get('backoff_multiplier', 2.0)
    )
    
    logger.info("Creating cleanup worker...")
    torrent_dir_path = downloader.torrent_dir if hasattr(downloader, 'torrent_dir') else os.path.expanduser("~/.movie_sync/torrents")
    cleanup_service = CleanupService(
        download_dir=config.get('download_directory', os.path.expanduser("~/Downloads")),
        torrent_dir=str(torrent_dir_path),
        qbt_manager=downloader.qbt_manager if hasattr(downloader, 'qbt_manager') else None
    )
    cleanup_worker = CleanupWorker(
        queue_manager=queue_manager,
        cleanup_service=cleanup_service,
        check_interval=3600,  # Check every hour
        grace_period=config.get('removal_grace_period', 604800),
        enabled=config.get('enable_removal_cleanup', False)
    )
    
    # Set up graceful shutdown
    shutdown_initiated = False
    
    def signal_handler(sig, frame):
        nonlocal shutdown_initiated
        if shutdown_initiated:
            logger.warning("Force shutdown - some data may be lost")
            sys.exit(1)
        
        shutdown_initiated = True
        logger.info("=" * 70)
        logger.info("Shutdown signal received - stopping workers...")
        logger.info("=" * 70)
        
        monitor_worker.stop()
        download_worker.stop()
        cleanup_worker.stop()
        
        logger.info("Waiting for workers to finish (max 10 seconds)...")
        monitor_worker.join(timeout=10)
        download_worker.join(timeout=10)
        cleanup_worker.join(timeout=10)

        # Show final statistics
        logger.info("=" * 70)
        logger.info("Final Statistics")
        logger.info("=" * 70)
        stats = queue_manager.get_statistics()
        logger.info(f"   Pending: {stats['pending']}")
        logger.info(f"   Failed: {stats['failed']}")
        logger.info(f"   Completed: {stats['completed']}")
        logger.info(f"   Removed: {stats['removed']}")
        logger.info(f"   Permanent failures: {stats['permanent_failures']}")
        
        if stats['permanent_failures'] > 0:
            logger.warning("Some movies have permanently failed after max retries")
            logger.info("   Check queue_failed.json in ~/.movie_sync/")
        
        logger.info("Shutdown complete - all queues saved")
        logger.info("=" * 70)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start worker threads
    logger.info("Starting workers...")
    monitor_worker.start()
    download_worker.start()
    cleanup_worker.start()
    
    logger.info("Workers started successfully")
    logger.info("=" * 70)
    
    # Keep main thread alive and show periodic statistics
    last_stats_time = time.time()
    stats_interval = 300  # Show stats every 5 minutes
    
    try:
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            current_time = time.time()
            if current_time - last_stats_time >= stats_interval:
                stats = queue_manager.get_statistics()
                if stats['pending'] > 0 or stats['failed'] > 0 or stats['removed'] > 0:
                    logger.info(f"Status: {stats['pending']} pending, "
                          f"{stats['failed']} failed, {stats['completed']} completed, "
                          f"{stats['removed']} removed")
                last_stats_time = current_time
    
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    
    return 0


def setup_configuration(config: dict):
    """
    Interactive configuration setup
    
    Args:
        config: Current configuration dictionary
    """
    print("\n" + "=" * 70)
    print("Movie Sync - Configuration Setup")
    print("=" * 70)
    
    # Letterboxd username
    print("\n1. Letterboxd Configuration")
    print("-" * 70)
    username = input(f"Letterboxd username [{config.get('username', '')}]: ").strip()
    if username:
        config["username"] = username
    
    # Check interval
    print("\n2. Monitoring Settings")
    print("-" * 70)
    print(f"Current check interval: {config.get('check_interval', 3600)}s ({config.get('check_interval', 3600)//60} minutes)")
    interval = input("Check interval in seconds [3600]: ").strip()
    if interval and interval.isdigit():
        config["check_interval"] = int(interval)
    
    # Download directory
    print("\n3. Download Settings")
    print("-" * 70)
    download_dir = input(f"Download directory [{config.get('download_directory', '~/Downloads')}]: ").strip()
    if download_dir:
        config["download_directory"] = os.path.expanduser(download_dir)
    
    # Retry settings
    print("\n4. Retry Configuration")
    print("-" * 70)
    print(f"Current retry interval: {config.get('retry_interval', 3600)}s ({config.get('retry_interval', 3600)//60} minutes)")
    retry_interval = input("Base retry interval in seconds [3600]: ").strip()
    if retry_interval and retry_interval.isdigit():
        config["retry_interval"] = int(retry_interval)
    
    print(f"Current max retries: {config.get('max_retries', 5)}")
    max_retries = input("Maximum retry attempts [5]: ").strip()
    if max_retries and max_retries.isdigit():
        config["max_retries"] = int(max_retries)
    
    # Save configuration
    print("\n" + "=" * 70)
    print("Saving configuration...")
    Config.save(config)
    logger.info("Configuration saved to ~/.movie_sync/config.json")
    print("=" * 70)
    
    # Show FileList.io credentials info
    print("\nNote: FileList.io credentials will be requested on first run")
    print("   They will be encrypted and stored in ~/.movie_sync/")
    print("\nYou can now run: python main.py")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Movie Sync - Automatically sync Letterboxd watchlist to FileList.io",
        epilog="""
Examples:
  %(prog)s                # Run the application
  %(prog)s --config       # Configure settings
  %(prog)s --stats        # Show queue statistics
  %(prog)s --log-file ~/logs/movie_sync.log --console-level DEBUG

Queue files are stored in: ~/.movie_sync/
  - queue_pending.json      (movies waiting to download)
  - queue_failed.json       (failed movies with retry info)
  - queue_completed.json    (successfully downloaded)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--config", action="store_true", 
                       help="Configure the application")
    parser.add_argument("--stats", action="store_true",
                       help="Show queue statistics and exit")
    parser.add_argument("--username", 
                       help="Letterboxd username (overrides config)")
    parser.add_argument("--interval", type=int,
                       help="Check interval in seconds (overrides config)")
    parser.add_argument("--log-file", 
                       help="Path to log file (default: ~/.movie_sync/movie_sync.log)")
    parser.add_argument("--console-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Minimum log level for console output (default: INFO)")
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(log_file=args.log_file, console_level=args.console_level)
    
    # Load configuration
    config = Config.load()
    
    # Handle configuration mode
    if args.config:
        setup_configuration(config)
        return 0
    
    # Handle stats mode
    if args.stats:
        logger.info("=" * 70)
        logger.info("Queue Statistics")
        logger.info("=" * 70)
        qm = QueueManager()
        stats = qm.get_statistics()
        
        logger.info(f"Pending:    {stats['pending']}")
        logger.info(f"Failed:     {stats['failed']}")
        logger.info(f"Completed:  {stats['completed']}")
        logger.info(f"Permanent:  {stats['permanent_failures']}")
        
        if stats['failed'] > 0:
            logger.info("Movies ready for retry:")
            ready = qm.get_movies_ready_for_retry(config.get('max_retries', 5))
            if ready:
                for movie in ready[:5]:  # Show first 5
                    logger.info(f"   - {movie['title']} (retry #{movie.get('retry_count', 0) + 1})")
                if len(ready) > 5:
                    logger.info(f"   ... and {len(ready) - 5} more")
            else:
                logger.info("   (none ready yet)")
        
        if stats['permanent_failures'] > 0:
            logger.info("Permanent failures:")
            failures = qm.get_permanent_failures(config.get('max_retries', 5))
            for movie in failures[:5]:  # Show first 5
                logger.info(f"   - {movie['title']}: {movie.get('last_error', 'Unknown error')}")
            if len(failures) > 5:
                logger.info(f"   ... and {len(failures) - 5} more")
        
        logger.info("=" * 70)
        return 0
    
    # Override config with command-line arguments
    if args.username:
        config["username"] = args.username
    if args.interval:
        config["check_interval"] = args.interval
    
    # Validate configuration
    if not config.get("username"):
        logger.error("Letterboxd username is required")
        logger.info("Run with --config to set up configuration: python main.py --config")
        return 1
    
    # Run the application
    return run_movie_sync(config)


if __name__ == "__main__":
    sys.exit(main())
