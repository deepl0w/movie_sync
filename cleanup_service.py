"""
Cleanup Service for Movie Sync
Handles deletion of torrents, files, and qBittorrent entries for removed movies
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from difflib import SequenceMatcher
import re

# Module logger
logger = logging.getLogger(__name__)


class CleanupService:
    """Service for cleaning up removed movies"""
    
    def __init__(self, download_dir: str, torrent_dir: str, qbt_manager=None):
        """
        Initialize cleanup service
        
        Args:
            download_dir: Directory where movies are downloaded
            torrent_dir: Directory where torrent files are stored
            qbt_manager: Optional qBittorrent manager instance
        """
        self.download_dir = Path(download_dir)
        self.torrent_dir = Path(torrent_dir)
        self.qbt_manager = qbt_manager
    
    def cleanup_movie(self, movie: Dict, delete_files: bool = True, 
                     delete_torrent: bool = True, remove_from_qbt: bool = True) -> Dict[str, bool]:
        """
        Clean up all traces of a movie
        
        Args:
            movie: Movie dictionary with title and year
            delete_files: Whether to delete downloaded movie files
            delete_torrent: Whether to delete torrent file
            remove_from_qbt: Whether to remove from qBittorrent
            
        Returns:
            Dictionary with cleanup results
        """
        results = {
            'files_deleted': False,
            'torrent_deleted': False,
            'qbt_removed': False,
            'errors': []
        }
        
        title = movie.get('title', '')
        year = movie.get('year', '')
        
        if not title:
            results['errors'].append('No title provided')
            return results
        
        # Delete downloaded files
        if delete_files and self.download_dir.exists():
            try:
                deleted = self._delete_movie_files(title, year)
                results['files_deleted'] = deleted
                if deleted:
                    logger.info(f"[DELETE]  Deleted movie files for: {title} ({year})")
            except Exception as e:
                error_msg = f"Error deleting files: {e}"
                results['errors'].append(error_msg)
                logger.warning(f"{error_msg}")
        
        # Delete torrent file
        if delete_torrent and self.torrent_dir.exists():
            try:
                deleted = self._delete_torrent_file(title, year)
                results['torrent_deleted'] = deleted
                if deleted:
                    logger.info(f"[DELETE]  Deleted torrent file for: {title} ({year})")
            except Exception as e:
                error_msg = f"Error deleting torrent: {e}"
                results['errors'].append(error_msg)
                logger.warning(f"{error_msg}")
        
        # Remove from qBittorrent
        if remove_from_qbt and self.qbt_manager and self.qbt_manager.client:
            try:
                removed = self._remove_from_qbittorrent(title, year)
                results['qbt_removed'] = removed
                if removed:
                    logger.info(f"[DELETE]  Removed from qBittorrent: {title} ({year})")
            except Exception as e:
                error_msg = f"Error removing from qBittorrent: {e}"
                results['errors'].append(error_msg)
                logger.warning(f"  {error_msg}")
        
        return results
    
    def _delete_movie_files(self, title: str, year: str) -> bool:
        """
        Delete movie files using fuzzy matching
        
        Args:
            title: Movie title
            year: Movie year
            
        Returns:
            True if files were deleted
        """
        normalized_title = self._normalize_title(title)
        deleted = False
        
        # Search for matching files/directories
        for item in self.download_dir.rglob('*'):
            if not (item.is_file() or item.is_dir()):
                continue
            
            item_name = item.name.lower()
            
            # Check for substring match
            if normalized_title in item_name:
                if year and str(year) in item_name:
                    self._safe_delete(item)
                    deleted = True
                elif not year:
                    self._safe_delete(item)
                    deleted = True
            else:
                # Fuzzy matching fallback
                title_part = self._extract_title_part(item_name)
                similarity = SequenceMatcher(None, normalized_title, title_part).ratio()
                
                if year and str(year) in item_name:
                    similarity += 0.10
                
                if similarity >= 0.85:
                    self._safe_delete(item)
                    deleted = True
        
        return deleted
    
    def _delete_torrent_file(self, title: str, year: str) -> bool:
        """
        Delete torrent file using fuzzy matching
        
        Args:
            title: Movie title
            year: Movie year
            
        Returns:
            True if torrent was deleted
        """
        normalized_title = self._normalize_title(title)
        deleted = False
        
        # Search for matching torrent files
        for torrent_file in self.torrent_dir.glob('*.torrent'):
            if not torrent_file.is_file():
                continue
            
            filename = torrent_file.stem.lower()
            
            # Check for substring match
            if normalized_title in filename:
                if year and str(year) in filename:
                    self._safe_delete(torrent_file)
                    deleted = True
                elif not year:
                    self._safe_delete(torrent_file)
                    deleted = True
            else:
                # Fuzzy matching fallback
                title_part = self._extract_title_part(filename)
                similarity = SequenceMatcher(None, normalized_title, title_part).ratio()
                
                if year and str(year) in filename:
                    similarity += 0.10
                
                if similarity >= 0.85:
                    self._safe_delete(torrent_file)
                    deleted = True
        
        return deleted
    
    def _remove_from_qbittorrent(self, title: str, year: str) -> bool:
        """
        Remove torrent from qBittorrent
        
        Args:
            title: Movie title
            year: Movie year
            
        Returns:
            True if torrent was removed
        """
        if not self.qbt_manager or not self.qbt_manager.client:
            return False
        
        normalized_title = self._normalize_title(title)
        
        try:
            # Get list of torrents from qBittorrent
            torrents = self.qbt_manager.client.torrents_info()
            
            for torrent in torrents:
                torrent_name = torrent.name.lower()
                
                # Check for substring match
                if normalized_title in torrent_name:
                    if year and str(year) in torrent_name:
                        # Remove torrent with files
                        self.qbt_manager.client.torrents_delete(
                            delete_files=True, 
                            torrent_hashes=torrent.hash
                        )
                        return True
                    elif not year:
                        self.qbt_manager.client.torrents_delete(
                            delete_files=True, 
                            torrent_hashes=torrent.hash
                        )
                        return True
                else:
                    # Fuzzy matching fallback
                    title_part = self._extract_title_part(torrent_name)
                    similarity = SequenceMatcher(None, normalized_title, title_part).ratio()
                    
                    if year and str(year) in torrent_name:
                        similarity += 0.10
                    
                    if similarity >= 0.85:
                        self.qbt_manager.client.torrents_delete(
                            delete_files=True, 
                            torrent_hashes=torrent.hash
                        )
                        return True
        
        except Exception as e:
            logger.warning(f"Error accessing qBittorrent: {e}")
            return False
        
        return False
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for matching"""
        return title.lower().replace(' ', '.').replace(':', '').replace("'", '')
    
    def _extract_title_part(self, filename: str) -> str:
        """Extract title portion from filename (before quality indicators)"""
        title_part = re.split(
            r'\d{3,4}p|bluray|brrip|webrip|hdtv|dvdrip|x264|x265|h264|h265',
            filename, 
            flags=re.IGNORECASE
        )[0]
        return title_part
    
    def _safe_delete(self, path: Path) -> None:
        """
        Safely delete a file or directory
        
        Args:
            path: Path to delete
        """
        try:
            if path.is_file():
                path.unlink()
                logger.debug(f"[DELETE]  Deleted file: {path.name}")
            elif path.is_dir():
                shutil.rmtree(path)
                logger.debug(f"[DELETE]  Deleted directory: {path.name}")
        except Exception as e:
            logger.warning(f"Could not delete {path.name}: {e}")
    
    def get_cleanup_preview(self, movie: Dict) -> Dict[str, List[str]]:
        """
        Preview what would be deleted for a movie (dry run)
        
        Args:
            movie: Movie dictionary with title and year
            
        Returns:
            Dictionary with lists of files/torrents that would be deleted
        """
        preview = {
            'files': [],
            'torrents': [],
            'qbt_torrents': []
        }
        
        title = movie.get('title', '')
        year = movie.get('year', '')
        
        if not title:
            return preview
        
        normalized_title = self._normalize_title(title)
        
        # Preview files
        if self.download_dir.exists():
            for item in self.download_dir.rglob('*'):
                if not (item.is_file() or item.is_dir()):
                    continue
                
                item_name = item.name.lower()
                
                if normalized_title in item_name and (not year or str(year) in item_name):
                    preview['files'].append(str(item))
        
        # Preview torrents
        if self.torrent_dir.exists():
            for torrent_file in self.torrent_dir.glob('*.torrent'):
                filename = torrent_file.stem.lower()
                
                if normalized_title in filename and (not year or str(year) in filename):
                    preview['torrents'].append(str(torrent_file))
        
        # Preview qBittorrent torrents
        if self.qbt_manager and self.qbt_manager.client:
            try:
                torrents = self.qbt_manager.client.torrents_info()
                for torrent in torrents:
                    torrent_name = torrent.name.lower()
                    
                    if normalized_title in torrent_name and (not year or str(year) in torrent_name):
                        preview['qbt_torrents'].append(torrent.name)
            except Exception as e:
                logger.warning(f"Error accessing qBittorrent: {e}")
        
        return preview
