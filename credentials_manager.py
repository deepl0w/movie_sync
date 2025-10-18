"""
Credentials Manager with Encryption
Securely stores and retrieves credentials for any service using encryption
"""

import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Tuple, Optional, Dict


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
        print(f"✓ {service.capitalize()} credentials saved securely")
    
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
            print(f"Warning: Could not read {service} credentials: {e}")
            return None, None
    
    def clear_credentials(self, service: str) -> None:
        """Delete stored credentials for a service
        
        Args:
            service: Service name (e.g., 'filelist', 'qbittorrent')
        """
        credentials_file = self._get_credentials_file(service)
        
        if credentials_file.exists():
            credentials_file.unlink()
            print(f"{service.capitalize()} credentials cleared.")
    
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


if __name__ == "__main__":
    # Test the credentials manager
    print("Testing Generic Credentials Manager")
    print("=" * 60)
    
    manager = CredentialsManager()
    
    # Test 1: Generic API for FileList.io
    print("\n1. Testing generic API with 'filelist' service...")
    manager.save_credentials("filelist", "testuser", "testpass123")
    username, password = manager.get_credentials("filelist")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else 'None'}")
    
    if username == "testuser" and password == "testpass123":
        print("✓ Generic API working for filelist")
    else:
        print("✗ Generic API test FAILED")
    
    # Test 2: Generic API for qBittorrent
    print("\n2. Testing generic API with 'qbittorrent' service...")
    manager.save_credentials("qbittorrent", "admin", "qbtpass456")
    username, password = manager.get_credentials("qbittorrent")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else 'None'}")
    
    if username == "admin" and password == "qbtpass456":
        print("✓ Generic API working for qbittorrent")
    else:
        print("✗ Generic API test FAILED")
    
    # Test 3: Generic API for custom service
    print("\n3. Testing generic API with custom 'myservice' service...")
    manager.save_credentials("myservice", "user123", "secret789")
    username, password = manager.get_credentials("myservice")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if password else 'None'}")
    
    if username == "user123" and password == "secret789":
        print("✓ Generic API working for custom service")
    else:
        print("✗ Generic API test FAILED")
    
    # Test 4: List all services
    print("\n4. Testing list_services()...")
    services = manager.list_services()
    print(f"Stored services: {', '.join(services)}")
    
    if set(services) == {"filelist", "qbittorrent", "myservice"}:
        print("✓ Service listing working")
    else:
        print("✗ Service listing test FAILED")
    
    # Test 5: Backward compatibility methods
    print("\n5. Testing backward compatibility methods...")
    manager.save_filelist_credentials("bcuser", "bcpass")
    username, password = manager.get_filelist_credentials()
    
    if username == "bcuser" and password == "bcpass":
        print("✓ Backward compatibility working")
    else:
        print("✗ Backward compatibility test FAILED")
    
    # Cleanup
    print("\n6. Cleaning up test credentials...")
    manager.clear_credentials("filelist")
    manager.clear_credentials("qbittorrent")
    manager.clear_credentials("myservice")
    print("\n✓ All tests complete!")
