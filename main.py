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

from config import Config
from queue_manager import QueueManager
from workers import MonitorWorker, DownloadWorker, CleanupWorker
from cleanup_service import CleanupService

try:
    from filelist_downloader import FileListDownloader
    FILELIST_AVAILABLE = True
except ImportError:
    FILELIST_AVAILABLE = False
    print("✗ FileList downloader not available")
    print("  Please install required packages: pip install -r requirements.txt")


def run_movie_sync(config: dict):
    """
    Run Movie Sync in threaded mode
    
    Args:
        config: Configuration dictionary
    """
    print("\n" + "=" * 70)
    print("🚀 MOVIE SYNC - Letterboxd to FileList.io")
    print("=" * 70)
    print(f"📺 Letterboxd user: {config['username']}")
    print(f"⏱️  Monitor interval: {config['check_interval']}s ({config['check_interval']//60} minutes)")
    print(f"🔄 Retry interval: {config.get('retry_interval', 3600)}s ({config.get('retry_interval', 3600)//60} minutes)")
    print(f"🔁 Max retries: {config.get('max_retries', 5)}")
    print(f"📁 Download directory: {config.get('download_directory', '~/Downloads')}")
    
    # Cleanup configuration
    cleanup_enabled = config.get('enable_removal_cleanup', False)
    grace_period = config.get('removal_grace_period', 604800)
    grace_days = grace_period // 86400
    print(f"🧹 Cleanup: {'ENABLED' if cleanup_enabled else 'DISABLED'} "
          f"(grace period: {grace_days} days)")
    
    print("\n💡 Press Ctrl+C to stop gracefully")
    print("=" * 70)
    
    # Check dependencies
    if not FILELIST_AVAILABLE:
        print("\n✗ Cannot start: FileList downloader not available")
        return 1
    
    # Initialize queue manager
    print("\n📋 Initializing queue manager...")
    queue_manager = QueueManager()
    
    # Initialize downloader
    print("⚙️  Initializing FileList downloader...")
    downloader = FileListDownloader(
        queue_file=None,  # Not used in threaded mode
        use_qbittorrent=True
    )
    
    # Create worker threads
    print("🎬 Creating monitor worker...")
    monitor_worker = MonitorWorker(
        username=config['username'],
        queue_manager=queue_manager,
        check_interval=config['check_interval'],
        watchlist_file=config.get('watchlist_file')
    )
    
    print("⬇️  Creating download worker...")
    download_worker = DownloadWorker(
        queue_manager=queue_manager,
        downloader=downloader,
        download_dir=config.get('download_directory', os.path.expanduser("~/Downloads")),
        retry_interval=config.get('retry_interval', 3600),
        max_retries=config.get('max_retries', 5),
        backoff_multiplier=config.get('backoff_multiplier', 2.0)
    )
    
    print("🧹 Creating cleanup worker...")
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
            print("\n⚠️  Force shutdown - some data may be lost")
            sys.exit(1)
        
        shutdown_initiated = True
        print("\n\n" + "=" * 70)
        print("🛑 Shutdown signal received - stopping workers...")
        print("=" * 70)
        
        monitor_worker.stop()
        download_worker.stop()
        cleanup_worker.stop()
        
        print("⏳ Waiting for workers to finish (max 10 seconds)...")
        monitor_worker.join(timeout=10)
        download_worker.join(timeout=10)
        cleanup_worker.join(timeout=10)

        # Show final statistics
        print("\n" + "=" * 70)
        print("📊 Final Statistics")
        print("=" * 70)
        stats = queue_manager.get_statistics()
        print(f"   Pending: {stats['pending']}")
        print(f"   Failed: {stats['failed']}")
        print(f"   Completed: {stats['completed']}")
        print(f"   Removed: {stats['removed']}")
        print(f"   Permanent failures: {stats['permanent_failures']}")
        
        if stats['permanent_failures'] > 0:
            print("\n⚠️  Some movies have permanently failed after max retries")
            print("   Check queue_failed.json in ~/.movie_sync/")
        
        print("\n✅ Shutdown complete - all queues saved")
        print("=" * 70)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start worker threads
    print("\n🚀 Starting workers...")
    monitor_worker.start()
    download_worker.start()
    cleanup_worker.start()
    
    print("✅ Workers started successfully")
    print("\n" + "=" * 70)
    
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
                    print(f"\n📊 Status: {stats['pending']} pending, "
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
    print("⚙️  Movie Sync - Configuration Setup")
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
    print("💾 Saving configuration...")
    Config.save(config)
    print("✅ Configuration saved to ~/.movie_sync/config.json")
    print("=" * 70)
    
    # Show FileList.io credentials info
    print("\n📝 Note: FileList.io credentials will be requested on first run")
    print("   They will be encrypted and stored in ~/.movie_sync/")
    print("\n🎬 You can now run: python main.py")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Movie Sync - Automatically sync Letterboxd watchlist to FileList.io",
        epilog="""
Examples:
  %(prog)s                # Run the application
  %(prog)s --config       # Configure settings
  %(prog)s --stats        # Show queue statistics

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
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.load()
    
    # Handle configuration mode
    if args.config:
        setup_configuration(config)
        return 0
    
    # Handle stats mode
    if args.stats:
        print("\n" + "=" * 70)
        print("📊 Queue Statistics")
        print("=" * 70)
        qm = QueueManager()
        stats = qm.get_statistics()
        
        print(f"\n📝 Pending:    {stats['pending']}")
        print(f"❌ Failed:     {stats['failed']}")
        print(f"✅ Completed:  {stats['completed']}")
        print(f"⛔ Permanent:  {stats['permanent_failures']}")
        
        if stats['failed'] > 0:
            print(f"\n🔄 Movies ready for retry:")
            ready = qm.get_movies_ready_for_retry(config.get('max_retries', 5))
            if ready:
                for movie in ready[:5]:  # Show first 5
                    print(f"   • {movie['title']} (retry #{movie.get('retry_count', 0) + 1})")
                if len(ready) > 5:
                    print(f"   ... and {len(ready) - 5} more")
            else:
                print("   (none ready yet)")
        
        if stats['permanent_failures'] > 0:
            print(f"\n⛔ Permanent failures:")
            failures = qm.get_permanent_failures(config.get('max_retries', 5))
            for movie in failures[:5]:  # Show first 5
                print(f"   • {movie['title']}: {movie.get('last_error', 'Unknown error')}")
            if len(failures) > 5:
                print(f"   ... and {len(failures) - 5} more")
        
        print("\n" + "=" * 70)
        return 0
    
    # Override config with command-line arguments
    if args.username:
        config["username"] = args.username
    if args.interval:
        config["check_interval"] = args.interval
    
    # Validate configuration
    if not config.get("username"):
        print("\n❌ Error: Letterboxd username is required")
        print("\n�� Run with --config to set up configuration:")
        print("   python main.py --config")
        return 1
    
    # Run the application
    return run_movie_sync(config)


if __name__ == "__main__":
    sys.exit(main())
