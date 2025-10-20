"""
Web Interface for Movie Sync
Provides a Flask-based web UI for monitoring and managing the application
"""

import threading
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any, Dict

try:
    from flask import Flask, render_template, jsonify, request, send_from_directory
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from queue_manager import QueueManager
from config import Config

# Module logger
logger = logging.getLogger(__name__)


class WebInterface(threading.Thread):
    """
    Web interface thread that runs Flask server
    Provides REST API and web UI for queue management
    """
    
    def __init__(self, queue_manager: QueueManager, port: int = 5000, 
                 host: str = "0.0.0.0", log_file: Optional[str] = None,
                 config_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                 cleanup_service = None, monitor_worker = None):
        """
        Initialize web interface
        
        Args:
            queue_manager: Shared queue manager instance
            port: Port to run Flask server on
            host: Host to bind to (default: 0.0.0.0 - all interfaces)
            log_file: Path to log file to display
            config_callback: Callback function to reload config in workers
            cleanup_service: CleanupService instance for force delete operations
            monitor_worker: MonitorWorker instance for triggering watchlist updates
        """
        super().__init__(daemon=True, name="WebInterface")
        
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for web interface. Install with: pip install flask flask-cors")
        
        self.queue_manager = queue_manager
        self.port = port
        self.host = host
        self.log_file = log_file
        self.config_callback = config_callback
        self.cleanup_service = cleanup_service
        self.monitor_worker = monitor_worker
        self.current_config = Config.load()
        self.app = Flask(__name__, template_folder='templates', static_folder='static')
        
        # Enable auto-reload for templates and static files in development
        self.app.config['TEMPLATES_AUTO_RELOAD'] = True
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for static files
        
        CORS(self.app)
        
        self.running = False
        self.server = None
        
        # Set up routes
        self._setup_routes()
        
        # Disable Flask's default logger to avoid duplicate logs
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
    
    def _setup_routes(self):
        """Set up Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template('index.html')
        
        @self.app.route('/api/stats')
        def get_stats():
            """Get queue statistics"""
            try:
                stats = self.queue_manager.get_statistics()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/queues')
        def get_queues():
            """Get all queues"""
            try:
                pending = self.queue_manager.pending_queue
                failed = self.queue_manager.failed_queue
                completed = self.queue_manager.completed_queue
                removed = self.queue_manager.removed_queue
                
                return jsonify({
                    "pending": pending,
                    "failed": failed,
                    "completed": completed,
                    "removed": removed
                })
            except Exception as e:
                logger.error(f"Error getting queues: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/queue/<queue_name>')
        def get_queue(queue_name):
            """Get specific queue"""
            try:
                queues = {
                    'pending': self.queue_manager.pending_queue,
                    'failed': self.queue_manager.failed_queue,
                    'completed': self.queue_manager.completed_queue,
                    'removed': self.queue_manager.removed_queue
                }
                
                if queue_name not in queues:
                    return jsonify({"error": "Invalid queue name"}), 400
                
                return jsonify(queues[queue_name])
            except Exception as e:
                logger.error(f"Error getting queue {queue_name}: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/move', methods=['POST'])
        def move_movie(movie_id):
            """Move movie between queues"""
            try:
                data = request.json
                target_queue = data.get('target_queue')
                
                if target_queue not in ['pending', 'failed', 'completed', 'removed']:
                    return jsonify({"error": "Invalid target queue"}), 400
                
                # Find movie in all queues
                movie = None
                source_queue = None
                
                for queue_name, queue in [
                    ('pending', self.queue_manager.pending_queue),
                    ('failed', self.queue_manager.failed_queue),
                    ('completed', self.queue_manager.completed_queue),
                    ('removed', self.queue_manager.removed_queue)
                ]:
                    for m in queue:
                        if str(m.get('id')) == movie_id:
                            movie = m
                            source_queue = queue_name
                            break
                    if movie:
                        break
                
                if not movie:
                    return jsonify({"error": "Movie not found"}), 404
                
                # Remove from source queue
                if source_queue == 'pending':
                    self.queue_manager.pending_queue.remove(movie)
                    self.queue_manager._save_json(self.queue_manager.pending_file, self.queue_manager.pending_queue)
                elif source_queue == 'failed':
                    self.queue_manager.failed_queue.remove(movie)
                    self.queue_manager._save_json(self.queue_manager.failed_file, self.queue_manager.failed_queue)
                elif source_queue == 'completed':
                    self.queue_manager.completed_queue.remove(movie)
                    self.queue_manager._save_json(self.queue_manager.completed_file, self.queue_manager.completed_queue)
                elif source_queue == 'removed':
                    self.queue_manager.removed_queue.remove(movie)
                    self.queue_manager._save_json(self.queue_manager.removed_file, self.queue_manager.removed_queue)
                
                # Clean up metadata when moving from removed
                if source_queue == 'removed':
                    # Remove removed-specific fields
                    if 'removed_at' in movie:
                        del movie['removed_at']
                    # Status will be set by the add_to_* methods
                
                # Add to target queue (saves automatically)
                if target_queue == 'pending':
                    self.queue_manager.add_to_pending(movie)
                elif target_queue == 'failed':
                    self.queue_manager.add_to_failed(movie, "Manually moved", 0)
                elif target_queue == 'completed':
                    self.queue_manager.add_to_completed(movie)
                elif target_queue == 'removed':
                    self.queue_manager.add_to_removed(movie)
                
                return jsonify({
                    "success": True,
                    "message": f"Moved {movie.get('title')} from {source_queue} to {target_queue}"
                })
            except Exception as e:
                logger.error(f"Error moving movie: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/delete', methods=['POST'])
        def delete_movie(movie_id):
            """Delete movie from all queues"""
            try:
                deleted = False
                movie_title = None
                
                for queue in [
                    self.queue_manager.pending_queue,
                    self.queue_manager.failed_queue,
                    self.queue_manager.completed_queue,
                    self.queue_manager.removed_queue
                ]:
                    for movie in queue:
                        if str(movie.get('id')) == movie_id:
                            movie_title = movie.get('title')
                            queue.remove(movie)
                            deleted = True
                            break
                    if deleted:
                        break
                
                if deleted:
                    # Queues save automatically when modified
                    return jsonify({
                        "success": True,
                        "message": f"Deleted {movie_title}"
                    })
                else:
                    return jsonify({"error": "Movie not found"}), 404
            except Exception as e:
                logger.error(f"Error deleting movie: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/retry', methods=['POST'])
        def retry_movie(movie_id):
            """Reset retry count for a movie"""
            try:
                found = False
                
                for movie in self.queue_manager.failed_queue:
                    if str(movie.get('id')) == movie_id:
                        self.queue_manager.reset_failed_movie(movie_id)
                        found = True
                        break
                
                if found:
                    return jsonify({
                        "success": True,
                        "message": "Reset retry count"
                    })
                else:
                    return jsonify({"error": "Movie not found in failed queue"}), 404
            except Exception as e:
                logger.error(f"Error resetting movie: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/skip', methods=['POST'])
        def skip_movie(movie_id):
            """Mark a movie as skipped"""
            try:
                found = False
                queue_to_save = None
                
                # Find movie in any queue and mark as skipped
                for queue, filepath in [
                    (self.queue_manager.pending_queue, self.queue_manager.pending_file),
                    (self.queue_manager.failed_queue, self.queue_manager.failed_file),
                    (self.queue_manager.completed_queue, self.queue_manager.completed_file),
                    (self.queue_manager.removed_queue, self.queue_manager.removed_file)
                ]:
                    for movie in queue:
                        if str(movie.get('id')) == movie_id:
                            movie['skipped'] = True
                            found = True
                            queue_to_save = (filepath, queue)
                            break
                    if found:
                        break
                
                if found and queue_to_save:
                    # Save the modified queue
                    self.queue_manager._save_json(queue_to_save[0], queue_to_save[1])
                    return jsonify({
                        "success": True,
                        "message": "Movie marked as skipped"
                    })
                else:
                    return jsonify({"error": "Movie not found"}), 404
            except Exception as e:
                logger.error(f"Error skipping movie: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/unskip', methods=['POST'])
        def unskip_movie(movie_id):
            """Remove skip flag from a movie"""
            try:
                found = False
                queue_to_save = None
                
                # Find movie in any queue and remove skip flag
                for queue, filepath in [
                    (self.queue_manager.pending_queue, self.queue_manager.pending_file),
                    (self.queue_manager.failed_queue, self.queue_manager.failed_file),
                    (self.queue_manager.completed_queue, self.queue_manager.completed_file),
                    (self.queue_manager.removed_queue, self.queue_manager.removed_file)
                ]:
                    for movie in queue:
                        if str(movie.get('id')) == movie_id:
                            movie['skipped'] = False
                            found = True
                            queue_to_save = (filepath, queue)
                            break
                    if found:
                        break
                
                if found and queue_to_save:
                    # Save the modified queue
                    self.queue_manager._save_json(queue_to_save[0], queue_to_save[1])
                    return jsonify({
                        "success": True,
                        "message": "Movie unskipped"
                    })
                else:
                    return jsonify({"error": "Movie not found"}), 404
            except Exception as e:
                logger.error(f"Error unskipping movie: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/force-download', methods=['POST'])
        def force_download_movie(movie_id):
            """Force download a movie (bypass space limit)"""
            try:
                found = False
                movie_title = "Unknown"
                source_queue = None
                
                # Find movie in pending queue
                for movie in self.queue_manager.pending_queue:
                    if str(movie.get('id')) == movie_id:
                        movie['force_download'] = True
                        movie_title = movie.get('title', 'Unknown')
                        found = True
                        source_queue = 'pending'
                        break
                
                # If not found in pending, check failed queue (for space limit failures)
                if not found:
                    for movie in self.queue_manager.failed_queue:
                        if str(movie.get('id')) == movie_id:
                            # Only allow force download for space limit failures
                            if movie.get('failed_reason') == 'space_limit':
                                movie_title = movie.get('title', 'Unknown')
                                # Remove from failed queue
                                self.queue_manager.failed_queue.remove(movie)
                                # Clear failed metadata and set force download flag
                                movie.pop('failed_reason', None)
                                movie.pop('last_error', None)
                                movie.pop('retry_count', None)
                                movie.pop('retry_after', None)
                                movie['force_download'] = True
                                # Add to pending queue
                                self.queue_manager.add_to_pending(movie)
                                found = True
                                source_queue = 'failed'
                                break
                            else:
                                return jsonify({"error": "Force download only available for space limit failures"}), 400
                
                if found:
                    if source_queue == 'pending':
                        # Save pending queue
                        self.queue_manager._save_json(
                            self.queue_manager.pending_file,
                            self.queue_manager.pending_queue
                        )
                    elif source_queue == 'failed':
                        # Save both queues
                        self.queue_manager._save_json(
                            self.queue_manager.failed_file,
                            self.queue_manager.failed_queue
                        )
                        self.queue_manager._save_json(
                            self.queue_manager.pending_file,
                            self.queue_manager.pending_queue
                        )
                    
                    return jsonify({
                        "success": True,
                        "message": f"Marked {movie_title} for forced download"
                    })
                else:
                    return jsonify({"error": "Movie not found in pending or failed queue"}), 404
            except Exception as e:
                logger.error(f"Error marking movie for force download: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/movie/<movie_id>/force-delete', methods=['POST'])
        def force_delete_movie(movie_id):
            """Force delete a movie immediately (bypass grace period)"""
            try:
                found = False
                movie_title = "Unknown"
                movie_data = None
                
                # Find movie in removed queue
                for movie in self.queue_manager.removed_queue:
                    if str(movie.get('id')) == movie_id:
                        movie_title = movie.get('title', 'Unknown')
                        movie_data = movie
                        found = True
                        break
                
                if not found:
                    return jsonify({"error": "Movie not found in removed queue"}), 404
                
                if not movie_data:
                    return jsonify({"error": "Movie data not available"}), 500
                
                # Use the cleanup service if available
                if not self.cleanup_service:
                    return jsonify({"error": "Cleanup service not available"}), 500
                
                try:
                    # Perform cleanup
                    results = self.cleanup_service.cleanup_movie(
                        movie_data,
                        delete_files=True,
                        delete_torrent=True,
                        remove_from_qbt=True
                    )
                    
                    # Remove from removed queue
                    self.queue_manager.remove_from_removed_queue(movie_id)
                    
                    # Build result message
                    deleted_items = []
                    if results.get('files_deleted'):
                        deleted_items.append(f"{results['files_deleted']} files")
                    if results.get('torrent_deleted'):
                        deleted_items.append("torrent file")
                    if results.get('qbt_removed'):
                        deleted_items.append("qBittorrent entry")
                    
                    if deleted_items:
                        message = f"Force deleted {movie_title}: " + ", ".join(deleted_items)
                    else:
                        message = f"No files found for {movie_title}, removed from queue"
                    
                    errors = results.get('errors', [])
                    if errors and isinstance(errors, list) and len(errors) > 0:
                        message += f" (with {len(errors)} errors)"
                    
                    logger.info(f"[FORCE DELETE] {message}")
                    
                    return jsonify({
                        "success": True,
                        "message": message,
                        "details": results
                    })
                    
                except ImportError as ie:
                    logger.error(f"Error importing cleanup service: {ie}")
                    return jsonify({"error": "Cleanup service not available"}), 500
                    
            except Exception as e:
                logger.error(f"Error force deleting movie: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/queue/reorder', methods=['POST'])
        def reorder_queue():
            """Reorder items in a queue"""
            try:
                data = request.get_json()
                queue_name = data.get('queue')
                dragged_id = str(data.get('dragged_id'))
                target_id = str(data.get('target_id'))
                
                # Get the appropriate queue
                queue_map = {
                    'pending': self.queue_manager.pending_queue,
                    'failed': self.queue_manager.failed_queue,
                    'completed': self.queue_manager.completed_queue,
                    'removed': self.queue_manager.removed_queue
                }
                
                if queue_name not in queue_map:
                    return jsonify({"error": "Invalid queue name"}), 400
                
                queue = queue_map[queue_name]
                
                # Find both movies
                dragged_movie = None
                dragged_index = -1
                target_index = -1
                
                for i, movie in enumerate(queue):
                    if str(movie.get('id')) == dragged_id:
                        dragged_movie = movie
                        dragged_index = i
                    if str(movie.get('id')) == target_id:
                        target_index = i
                
                if dragged_index == -1 or target_index == -1:
                    return jsonify({"error": "Movies not found"}), 404
                
                if dragged_movie is None:
                    return jsonify({"error": "Dragged movie not found"}), 404
                
                # Remove dragged item
                queue.pop(dragged_index)
                
                # Adjust target index if needed
                if dragged_index < target_index:
                    target_index -= 1
                
                # Insert at new position
                queue.insert(target_index, dragged_movie)
                
                # Save the reordered queue to file
                file_map = {
                    'pending': self.queue_manager.pending_file,
                    'failed': self.queue_manager.failed_file,
                    'completed': self.queue_manager.completed_file,
                    'removed': self.queue_manager.removed_file
                }
                self.queue_manager._save_json(file_map[queue_name], queue)
                
                return jsonify({
                    "success": True,
                    "message": "Queue reordered"
                })
            except Exception as e:
                logger.error(f"Error reordering queue: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/logs')
        def get_logs():
            """Get recent log entries"""
            try:
                if not self.log_file or not os.path.exists(self.log_file):
                    return jsonify({"logs": []})
                
                # Read last 100 lines
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                return jsonify({"logs": recent_lines})
            except Exception as e:
                logger.error(f"Error reading logs: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/config')
        def get_config():
            """Get current configuration"""
            try:
                self.current_config = Config.load()
                # Add config descriptions for the UI
                config_with_meta = {
                    "config": self.current_config,
                    "meta": {
                        "username": {"type": "text", "label": "Letterboxd Username", "description": "Your Letterboxd username"},
                        "check_interval": {"type": "number", "label": "Check Interval (seconds)", "description": "How often to check watchlist", "min": 60},
                        "download_directory": {"type": "text", "label": "Download Directory", "description": "Where to save downloaded files"},
                        "max_download_space_gb": {"type": "number", "label": "Max Download Space (GB)", "description": "Maximum space for downloads (0 = unlimited)", "min": 0},
                        "retry_interval": {"type": "number", "label": "Retry Interval (seconds)", "description": "Base interval for retrying failed downloads", "min": 60},
                        "max_retries": {"type": "number", "label": "Max Retries", "description": "Maximum retry attempts before giving up", "min": 1},
                        "backoff_multiplier": {"type": "number", "label": "Backoff Multiplier", "description": "Exponential backoff multiplier", "min": 1, "step": 0.1},
                        "enable_removal_cleanup": {"type": "boolean", "label": "Enable Cleanup", "description": "Automatically delete removed movies"},
                        "removal_grace_period": {"type": "number", "label": "Grace Period (seconds)", "description": "Time before deleting removed movies", "min": 0}
                    }
                }
                return jsonify(config_with_meta)
            except Exception as e:
                logger.error(f"Error getting config: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """Update configuration"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No data provided"}), 400
                
                # Load current config
                current = Config.load()
                
                # Update only provided fields
                for key, value in data.items():
                    if key in Config.DEFAULT_CONFIG:
                        # Type validation
                        expected_type = type(Config.DEFAULT_CONFIG[key])
                        if not isinstance(value, expected_type):
                            try:
                                value = expected_type(value)
                            except (ValueError, TypeError):
                                return jsonify({"error": f"Invalid type for {key}"}), 400
                        current[key] = value
                
                # Save config
                Config.save(current)
                self.current_config = current
                
                # Notify workers of config change
                if self.config_callback:
                    try:
                        self.config_callback(current)
                        logger.info("[CONFIG] Configuration reloaded in workers")
                    except Exception as e:
                        logger.error(f"Error reloading config in workers: {e}")
                
                return jsonify({
                    "success": True,
                    "message": "Configuration updated successfully",
                    "config": current
                })
            except Exception as e:
                logger.error(f"Error updating config: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/update-watchlist', methods=['POST'])
        def update_watchlist():
            """Trigger an immediate watchlist update"""
            try:
                if not self.monitor_worker:
                    return jsonify({
                        "success": False,
                        "error": "Monitor worker not available"
                    }), 400
                
                # Trigger the watchlist check
                logger.info("[WEB] Force update watchlist triggered from web interface")
                self.monitor_worker._check_watchlist()
                
                return jsonify({
                    "success": True,
                    "message": "Watchlist updated successfully"
                })
            except Exception as e:
                logger.error(f"Error updating watchlist: {e}")
                return jsonify({"error": str(e)}), 500
    
    def run(self):
        """Main thread loop - runs Flask server"""
        self.running = True
        logger.info(f"[WEB]  Web interface starting on http://{self.host}:{self.port}")
        
        try:
            # Run Flask with minimal logging
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            logger.error(f"Web interface error: {e}")
        finally:
            self.running = False
            logger.info("[WEB]  Web interface stopped")
    
    def stop(self):
        """Stop the web interface"""
        logger.info("[STOP]  Stopping web interface...")
        self.running = False
        # Flask doesn't have a clean shutdown method when run this way
        # The daemon thread will be killed when main thread exits
