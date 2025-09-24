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
