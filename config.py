import os
from typing import Dict, Any
from pathlib import Path
import logging

# Module logger
logger = logging.getLogger(__name__)

class Config:
    # Config directory
    CONFIG_DIR = Path(os.path.expanduser("~/.movie_sync"))
    
    # Default configuration
    DEFAULT_CONFIG = {
        "username": "",
        "watchlist_file": str(CONFIG_DIR / "watchlist.json"),
        "check_interval": 3600,  # 1 hour
        "download_directory": os.path.expanduser("~/Downloads"),
        # Retry configuration
        "retry_interval": 3600,  # Base retry interval (1 hour)
        "max_retries": 5,  # Maximum retry attempts
        "backoff_multiplier": 2.0,  # Exponential backoff multiplier
        # Threading
        "use_threads": True,  # Enable threaded mode
        # Cleanup/Deletion configuration
        "enable_removal_cleanup": False,  # Toggle for automatic deletion of removed movies
        "removal_grace_period": 604800,  # Grace period before deletion (7 days in seconds)
    }
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load configuration from config file or use defaults"""
        # Ensure config directory exists
        Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        config_file = Config.CONFIG_DIR / "config.json"
        config = Config.DEFAULT_CONFIG.copy()
        
        if config_file.exists():
            try:
                import json
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    config.update(loaded_config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        return config
    
    @staticmethod
    def save(config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        # Ensure config directory exists
        Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        config_file = Config.CONFIG_DIR / "config.json"
        try:
            import json
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")