"""
Logging utility for movie_sync
Provides a simple way to get configured loggers for each module
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
