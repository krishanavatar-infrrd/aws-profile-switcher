"""
Configuration management for AWS Profile Manager
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = Path(config_file)
        self.config = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from JSON file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info("Configuration loaded successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                return False
        else:
            logger.warning(f"Configuration file {self.config_file} not found")
            return False
    
    def save_config(self) -> bool:
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value
    
    def get_environments(self) -> Dict[str, Any]:
        """Get environments configuration"""
        return self.config.get('environments', {})
    
    def get_assume_role_configs(self) -> Dict[str, Any]:
        """Get assume role configurations"""
        return self.config.get('assume_role_configs', {})
    
    def get_credentials_profiles(self) -> Dict[str, Any]:
        """Get credentials profiles configuration"""
        return self.config.get('credentials_profiles', {})
    
    def get_base_credentials_path(self) -> str:
        """Get base credentials path"""
        return self.config.get('base_credentials_path', '')

    def get_predefined_buckets(self) -> list:
        """Get predefined buckets configuration"""
        return self.config.get('predefined_buckets', [])

    def get_efs_connections(self) -> list:
        """Get all EFS connections"""
        connections = self.config.get('efs_connections', [])
        # Ensure name exists for all connections
        updated = False
        for i, conn in enumerate(connections):
            if 'name' not in conn:
                conn['name'] = f"Connection {i+1}"
                updated = True
        if updated:
            self.save_config()
        return connections

    def add_efs_connection(self, host: str, username: str, key_path: str = '', name: str = '') -> bool:
        """Add a new EFS connection"""
        if 'efs_connections' not in self.config:
            self.config['efs_connections'] = []
        
        if not name:
            name = f"Connection {len(self.config['efs_connections']) + 1}"
            
        connection = {
            'name': name,
            'host': host,
            'username': username,
            'key_path': key_path
        }
        
        self.config['efs_connections'].append(connection)
        return self.save_config()

    def update_efs_connection(self, index: int, host: str, username: str, key_path: str = '', name: str = '') -> bool:
        """Update an existing EFS connection"""
        connections = self.config.get('efs_connections', [])
        if 0 <= index < len(connections):
            connections[index] = {
                'name': name or connections[index].get('name', f"Connection {index+1}"),
                'host': host,
                'username': username,
                'key_path': key_path
            }
            self.config['efs_connections'] = connections
            return self.save_config()
        return False

    def remove_efs_connection(self, index: int) -> bool:
        """Remove EFS connection by index"""
        connections = self.config.get('efs_connections', [])
        if 0 <= index < len(connections):
            connections.pop(index)
            self.config['efs_connections'] = connections
            return self.save_config()
        return False

    def get_efs_config(self, index: int = 0) -> Dict[str, Any]:
        """Get EFS configuration by index (legacy support)"""
        connections = self.get_efs_connections()
        if 0 <= index < len(connections):
            return connections[index]
        return self.config.get('efs_config', {}) # Fallback to old single config if it exists



def get_region_display_name(region_code: str) -> str:
    """Get human-readable region name"""
    region_mapping = {
        'us-east-1': 'US East 1 (N. Virginia)',
        'us-east-2': 'US East 2 (Ohio)',
        'us-west-1': 'US West 1 (N. California)',
        'us-west-2': 'US West 2 (Oregon)',
        'eu-west-1': 'Europe West 1 (Ireland)',
        'eu-west-2': 'Europe West 2 (London)',
        'eu-west-3': 'Europe West 3 (Paris)',
        'eu-central-1': 'Europe Central 1 (Frankfurt)',
        'ap-southeast-1': 'Asia Pacific 1 (Singapore)',
        'ap-southeast-2': 'Asia Pacific 2 (Sydney)',
        'ap-northeast-1': 'Asia Pacific 3 (Tokyo)',
        'ap-northeast-2': 'Asia Pacific 4 (Seoul)',
        'ap-south-1': 'Asia Pacific 5 (Mumbai)',
        'ca-central-1': 'Canada Central 1 (Toronto)',
        'sa-east-1': 'South America 1 (São Paulo)'
    }
    return region_mapping.get(region_code, region_code)
