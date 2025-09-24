"""
AWS Role Assumption Management
"""

import configparser
from pathlib import Path
from typing import Dict, Optional, Union

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from aws_profile_manager.utils.logging import LoggerMixin


class AWSRoleManager(LoggerMixin):
    """Manages AWS role assumption and role-based profiles"""
    
    def __init__(self):
        self.config_path = Path.home() / '.aws' / 'config'
        self.credentials_path = Path.home() / '.aws' / 'credentials'
    
    def assume_role(self, role_arn: str, session_name: str, external_id: Optional[str] = None, duration: int = 3600) -> Dict[str, Union[bool, str, Dict]]:
        """Assume an AWS role and get temporary credentials"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            # Create STS client
            sts_client = boto3.client('sts')
            
            # Prepare assume role parameters
            assume_role_params = {
                'RoleArn': role_arn,
                'RoleSessionName': session_name,
                'DurationSeconds': duration
            }
            
            if external_id:
                assume_role_params['ExternalId'] = external_id
            
            # Assume the role
            response = sts_client.assume_role(**assume_role_params)
            
            credentials = response['Credentials']
            
            self.logger.info(f"Successfully assumed role: {role_arn}")
            
            return {
                'success': True,
                'message': 'Role assumed successfully',
                'credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration'].isoformat()
                }
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            self.logger.error(f"Failed to assume role: {error_code} - {error_message}")
            
            return {
                'success': False,
                'message': f"AWS Error: {error_code} - {error_message}"
            }
            
        except NoCredentialsError:
            self.logger.error("No AWS credentials found")
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error assuming role: {e}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    def save_role_profile(self, profile_name: str, role_arn: str, source_profile: str, region: str = 'us-east-1', external_id: Optional[str] = None) -> bool:
        """Save a role-based profile to AWS config"""
        try:
            # Create .aws directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing config
            config = configparser.ConfigParser()
            if self.config_path.exists():
                config.read(self.config_path)
            
            # Create or update profile section
            profile_section = f'profile {profile_name}'
            if not config.has_section(profile_section):
                config.add_section(profile_section)
            
            config.set(profile_section, 'role_arn', role_arn)
            config.set(profile_section, 'source_profile', source_profile)
            config.set(profile_section, 'region', region)
            
            if external_id:
                config.set(profile_section, 'external_id', external_id)
            
            # Write to file
            with open(self.config_path, 'w') as f:
                config.write(f)
            
            self.logger.info(f"Role profile saved: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save role profile: {e}")
            return False
    
    def list_role_profiles(self) -> Dict[str, Dict[str, str]]:
        """List all role-based profiles"""
        role_profiles = {}
        
        if not self.config_path.exists():
            return role_profiles
        
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            for section in config.sections():
                if section.startswith('profile '):
                    profile_name = section[8:]  # Remove 'profile ' prefix
                    role_profiles[profile_name] = dict(config[section])
            
        except Exception as e:
            self.logger.error(f"Failed to list role profiles: {e}")
        
        return role_profiles
    
    def remove_role_profile(self, profile_name: str) -> bool:
        """Remove a role-based profile"""
        try:
            if not self.config_path.exists():
                return True
            
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            profile_section = f'profile {profile_name}'
            if config.has_section(profile_section):
                config.remove_section(profile_section)
                
                with open(self.config_path, 'w') as f:
                    config.write(f)
                
                self.logger.info(f"Role profile removed: {profile_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove role profile: {e}")
            return False
