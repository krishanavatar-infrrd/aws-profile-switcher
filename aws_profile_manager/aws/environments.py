"""
AWS Environment Management
"""

import configparser
from pathlib import Path
from typing import Dict, Optional

from aws_profile_manager.core.config import ConfigManager, get_region_display_name
from aws_profile_manager.utils.logging import LoggerMixin


class EnvironmentManager(LoggerMixin):
    """Manages AWS environments and environment switching"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.config_path = Path.home() / '.aws' / 'config'
    
    def switch_environment(self, env_name: str) -> bool:
        """Switch to a specific environment by updating only the [profile default] section"""
        self.logger.info(f"Switching to {env_name.upper()} environment")

        environments = self.config_manager.get_environments()
        if env_name not in environments:
            self.logger.error(f"Environment {env_name} not found in configuration")
            return False

        env_config = environments[env_name]

        try:
            # Create .aws directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Read existing config
            config = configparser.ConfigParser()
            if self.config_path.exists():
                config.read(self.config_path)

            # Update ONLY the [profile default] section - don't create multiple profiles
            if not config.has_section('profile default'):
                config.add_section('profile default')

            # Set the environment configuration
            config.set('profile default', 'role_arn', env_config['role_arn'])
            config.set('profile default', 'region', env_config['region'])
            config.set('profile default', 'source_profile', 'infrrd-master')
            config.set('profile default', 'duration_seconds', '3600')

            # Remove any other profile sections that might conflict
            sections_to_remove = []
            for section in config.sections():
                if section.startswith('profile ') and section != 'profile default':
                    sections_to_remove.append(section)

            for section in sections_to_remove:
                config.remove_section(section)
                self.logger.info(f"Removed conflicting profile: {section}")

            # Write to file
            with open(self.config_path, 'w') as f:
                config.write(f)

            self.logger.info(f"Switched to {env_name.upper()} environment")
            self.logger.info(f"Updated [profile default] with role_arn: {env_config['role_arn']}")
            self.logger.info(f"Updated [profile default] with region: {env_config['region']}")
            self.logger.info(f"Updated [profile default] with source_profile: infrrd-master")
            return True

        except Exception as e:
            self.logger.error(f"Failed to switch environment: {e}")
            return False
    
    def list_environments(self) -> Dict[str, Dict[str, str]]:
        """List all available environments"""
        environments = self.config_manager.get_environments()
        result = {}
        
        for env_name, env_config in environments.items():
            region_display = get_region_display_name(env_config['region'])
            result[env_name] = {
                'region': env_config['region'],
                'region_display': region_display,
                'role_arn': env_config['role_arn'],
                'description': env_config.get('description', '')
            }
        
        return result
    
    def get_current_environment(self) -> Optional[str]:
        """Get current environment from AWS config file by checking [profile default]"""
        try:
            if not self.config_path.exists():
                return None
            
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            if 'profile default' not in config.sections():
                return None
            
            default_config = config['profile default']
            current_role_arn = default_config.get('role_arn', '')
            current_region = default_config.get('region', '')
            
            # Find matching environment
            environments = self.config_manager.get_environments()
            for env_name, env_config in environments.items():
                if (env_config['role_arn'] == current_role_arn and 
                    env_config['region'] == current_region):
                    return env_name
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get current environment: {e}")
            return None
    
    def add_environment(self, env_name: str, region: str, role_arn: str, description: str = '') -> bool:
        """Add a new environment"""
        try:
            environments = self.config_manager.get_environments()
            environments[env_name] = {
                'region': region,
                'role_arn': role_arn,
                'description': description
            }
            
            self.config_manager.set('environments', environments)
            return self.config_manager.save_config()
            
        except Exception as e:
            self.logger.error(f"Failed to add environment: {e}")
            return False
    
    def update_environment(self, env_name: str, region: str = None, role_arn: str = None, description: str = None) -> bool:
        """Update an existing environment"""
        try:
            environments = self.config_manager.get_environments()
            
            if env_name not in environments:
                self.logger.error(f"Environment {env_name} not found")
                return False
            
            if region is not None:
                environments[env_name]['region'] = region
            if role_arn is not None:
                environments[env_name]['role_arn'] = role_arn
            if description is not None:
                environments[env_name]['description'] = description
            
            self.config_manager.set('environments', environments)
            return self.config_manager.save_config()
            
        except Exception as e:
            self.logger.error(f"Failed to update environment: {e}")
            return False
    
    def remove_environment(self, env_name: str) -> bool:
        """Remove an environment"""
        try:
            environments = self.config_manager.get_environments()
            
            if env_name in environments:
                del environments[env_name]
                self.config_manager.set('environments', environments)
                return self.config_manager.save_config()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove environment: {e}")
            return False
