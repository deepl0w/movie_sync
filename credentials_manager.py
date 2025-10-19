"""
Credentials Manager with Encryption
Securely stores and retrieves credentials for any service using encryption
"""

import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Tuple, Optional, Dict
import logging

# Module logger
logger = logging.getLogger(__name__)


class CredentialsManager:
    """Manage encrypted credentials for multiple services"""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.movie_sync")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.key_file = self.config_dir / ".key"
        
        # Generate or load encryption key
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self) -> bytes:
        """Get existing encryption key or create a new one"""
        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(key)
            # Set restrictive permissions (owner read/write only)
            os.chmod(self.key_file, 0o600)
            return key
    
    def _get_credentials_file(self, service: str) -> Path:
        """Get the credentials file path for a service"""
        return self.config_dir / f"{service}_credentials.enc"
    
    def save_credentials(self, service: str, username: str, password: str) -> None:
        """Save credentials for a service with encryption
        
        Args:
            service: Service name (e.g., 'filelist', 'qbittorrent')
            username: Username for the service
            password: Password or passkey for the service
        """
        credentials = {
            "username": username,
            "password": password
        }
        
        # Convert to JSON and encrypt
        json_data = json.dumps(credentials).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        
        # Save encrypted data
        credentials_file = self._get_credentials_file(service)
        with open(credentials_file, "wb") as f:
            f.write(encrypted_data)
        
        # Set restrictive permissions
        os.chmod(credentials_file, 0o600)
        logger.info(f"{service.capitalize()} credentials saved securely")
    
    def get_credentials(self, service: str) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve and decrypt credentials for a service
        
        Args:
            service: Service name (e.g., 'filelist', 'qbittorrent')
            
        Returns:
            Tuple of (username, password) or (None, None) if not found
        """
        credentials_file = self._get_credentials_file(service)
        
        if not credentials_file.exists():
            return None, None
        
        try:
            # Read and decrypt
            with open(credentials_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            return credentials.get("username"), credentials.get("password")
            
        except Exception as e:
            logger.warning(f"Warning: Could not read {service} credentials: {e}")
            return None, None
    
    def clear_credentials(self, service: str) -> None:
        """Delete stored credentials for a service
        
        Args:
            service: Service name (e.g., 'filelist', 'qbittorrent')
        """
        credentials_file = self._get_credentials_file(service)
        
        if credentials_file.exists():
            credentials_file.unlink()
            logger.info(f"{service.capitalize()} credentials cleared.")
    
    def credentials_exist(self, service: str) -> bool:
        """Check if credentials are stored for a service
        
        Args:
            service: Service name (e.g., 'filelist', 'qbittorrent')
            
        Returns:
            True if credentials exist, False otherwise
        """
        credentials_file = self._get_credentials_file(service)
        return credentials_file.exists()
    
    def list_services(self) -> list:
        """List all services with stored credentials
        
        Returns:
            List of service names
        """
        services = []
        for file in self.config_dir.glob("*_credentials.enc"):
            service_name = file.stem.replace("_credentials", "")
            services.append(service_name)
        return services
    
    # Convenience methods for backward compatibility
    
    def save_filelist_credentials(self, username: str, password: str) -> None:
        """Save FileList.io credentials (convenience wrapper)"""
        self.save_credentials("filelist", username, password)
    
    def get_filelist_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get FileList.io credentials (convenience wrapper)"""
        return self.get_credentials("filelist")
    
    def clear_filelist_credentials(self) -> None:
        """Clear FileList.io credentials (convenience wrapper)"""
        self.clear_credentials("filelist")
    
    def filelist_credentials_exist(self) -> bool:
        """Check if FileList.io credentials exist (convenience wrapper)"""
        return self.credentials_exist("filelist")
    
    def save_qbittorrent_credentials(self, username: str, password: str) -> None:
        """Save qBittorrent credentials (convenience wrapper)"""
        self.save_credentials("qbittorrent", username, password)
    
    def get_qbittorrent_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get qBittorrent credentials (convenience wrapper)"""
        return self.get_credentials("qbittorrent")
    
    def clear_qbittorrent_credentials(self) -> None:
        """Clear qBittorrent credentials (convenience wrapper)"""
        self.clear_credentials("qbittorrent")
    
    def qbittorrent_credentials_exist(self) -> bool:
        """Check if qBittorrent credentials exist (convenience wrapper)"""
        return self.credentials_exist("qbittorrent")