"""
AWS Credentials Management
"""

import os
import re
import configparser
from pathlib import Path
from typing import Dict, Optional, Tuple

from aws_profile_manager.utils.logging import LoggerMixin


class AWSCredentialsManager(LoggerMixin):
    """Manages AWS credentials and profiles"""
    
    def __init__(self):
        self.credentials_path = Path.home() / '.aws' / 'credentials'
        self.config_path = Path.home() / '.aws' / 'config'
        self.current_profile = None
    
    def sync_credentials_from_base(self, base_credentials_path: Path) -> bool:
        """Sync credentials from base file to AWS credentials file"""
        self.logger.info("Syncing credentials from base file")
        
        if not base_credentials_path.exists():
            self.logger.error(f"Base credentials file not found: {base_credentials_path}")
            return False
        
        try:
            # Read base credentials
            with open(base_credentials_path, 'r') as f:
                base_content = f.read()
            
            # Parse credentials from the base file
            base_credentials = self._parse_credentials(base_content)
            
            if not base_credentials:
                self.logger.error("No valid credentials found in base file")
                return False
            
            # Get the first profile's credentials or 'default' profile credentials
            source_creds = None
            if 'default' in base_credentials:
                source_creds = base_credentials['default']
            else:
                # Take the first available profile
                source_creds = next(iter(base_credentials.values()))
            
            if not source_creds or 'aws_access_key_id' not in source_creds:
                self.logger.error("No valid AWS credentials found in base file")
                return False
            
            # Create credentials dictionary with both default and infrrd-master profiles
            credentials_to_write = {
                'default': source_creds.copy(),
                'infrrd-master': source_creds.copy()
            }
            
            # Update AWS credentials file
            return self._update_credentials_file(credentials_to_write)
            
        except Exception as e:
            self.logger.error(f"Failed to sync credentials: {e}")
            return False
    
    def _parse_credentials(self, content: str) -> Dict[str, Dict[str, str]]:
        """Parse credentials from base file content"""
        credentials = {}
        current_profile = None
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                current_profile = line[1:-1]
                credentials[current_profile] = {}
            elif '=' in line and current_profile:
                key, value = line.split('=', 1)
                credentials[current_profile][key.strip()] = value.strip()
        
        return credentials
    
    def _update_credentials_file(self, credentials: Dict[str, Dict[str, str]]) -> bool:
        """Update AWS credentials file with new credentials"""
        try:
            # Create .aws directory if it doesn't exist
            self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write credentials to file
            with open(self.credentials_path, 'w') as f:
                for profile_name, creds in credentials.items():
                    f.write(f'[{profile_name}]\n')
                    for key, value in creds.items():
                        f.write(f'{key}={value}\n')
                    f.write('\n')
            
            self.logger.info(f"Credentials file updated successfully with profiles: {list(credentials.keys())}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update credentials file: {e}")
            return False
    
    def get_current_profile(self) -> Optional[str]:
        """Get current AWS profile"""
        return os.environ.get('AWS_PROFILE', 'default')
    
    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a specific profile"""
        try:
            os.environ['AWS_PROFILE'] = profile_name
            self.current_profile = profile_name
            self.logger.info(f"Switched to profile: {profile_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to switch profile: {e}")
            return False
    
    def _get_profile_status(self, profile_data: Dict[str, str]) -> str:
        """Determine profile status"""
        if 'role_arn' in profile_data and 'aws_access_key_id' in profile_data:
            return 'both'
        elif 'role_arn' in profile_data:
            return 'role'
        elif 'aws_access_key_id' in profile_data:
            return 'valid'
        else:
            return 'invalid'
    
    def list_profiles(self) -> Dict[str, Dict[str, str]]:
        """List all available profiles with type information"""
        profiles = {}
        
        # Read credentials file
        if self.credentials_path.exists():
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            for section in config.sections():
                profile_data = dict(config[section])
                # Determine profile type
                if 'role_arn' in profile_data:
                    profile_data['type'] = 'role'
                elif 'aws_access_key_id' in profile_data:
                    profile_data['type'] = 'credentials'
                else:
                    profile_data['type'] = 'unknown'
                
                profile_data['status'] = self._get_profile_status(profile_data)
                profiles[section] = profile_data
        
        # Also check config file for role profiles
        if self.config_path.exists():
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            for section in config.sections():
                if section.startswith('profile '):
                    profile_name = section[8:]  # Remove 'profile ' prefix
                    if profile_name not in profiles:
                        profile_data = dict(config[section])
                        profile_data['type'] = 'role'
                        profile_data['status'] = self._get_profile_status(profile_data)
                        profiles[profile_name] = profile_data
                    else:
                        # Update existing profile with role info
                        profiles[profile_name].update(dict(config[section]))
                        if 'role_arn' in dict(config[section]):
                            profiles[profile_name]['type'] = 'both'  # Has both credentials and role
                            profiles[profile_name]['status'] = self._get_profile_status(profiles[profile_name])
        
        return profiles
    
    def save_credentials(self, profile_name: str, access_key: str, secret_key: str, session_token: str = None) -> bool:
        """Save credentials for a profile"""
        try:
            # Create .aws directory if it doesn't exist
            self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing credentials
            config = configparser.ConfigParser()
            if self.credentials_path.exists():
                config.read(self.credentials_path)
            
            # Update or create profile
            if not config.has_section(profile_name):
                config.add_section(profile_name)
            
            config.set(profile_name, 'aws_access_key_id', access_key)
            config.set(profile_name, 'aws_secret_access_key', secret_key)
            
            if session_token:
                config.set(profile_name, 'aws_session_token', session_token)
            
            # Write to file
            with open(self.credentials_path, 'w') as f:
                config.write(f)
            
            self.logger.info(f"Credentials saved for profile: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            return False
    
    def remove_profile(self, profile_name: str) -> bool:
        """Remove a profile"""
        try:
            if not self.credentials_path.exists():
                return True
            
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            if config.has_section(profile_name):
                config.remove_section(profile_name)
                
                with open(self.credentials_path, 'w') as f:
                    config.write(f)
                
                self.logger.info(f"Profile removed: {profile_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove profile: {e}")
            return False
