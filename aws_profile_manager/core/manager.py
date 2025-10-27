"""
Main AWS Profile Manager
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from aws_profile_manager.core.config import ConfigManager
from aws_profile_manager.aws.credentials import AWSCredentialsManager
from aws_profile_manager.aws.environments import EnvironmentManager
from aws_profile_manager.roles.assume_role import AWSRoleManager
from aws_profile_manager.s3.manager import S3Manager
from aws_profile_manager.utils.logging import LoggerMixin, setup_logging


class AWSProfileManager(LoggerMixin):
    """Main AWS Profile Manager that coordinates all operations"""
    
    def __init__(self, config_file: str = 'config.json'):
        # Setup logging
        setup_logging()
        
        # Initialize components
        self.config_manager = ConfigManager(config_file)
        self.credentials_manager = AWSCredentialsManager()
        self.environment_manager = EnvironmentManager(self.config_manager)
        self.role_manager = AWSRoleManager()
        self.s3_manager = S3Manager()
        
        self.logger.info("AWS Profile Manager initialized")
    
    def sync_credentials(self) -> bool:
        """Sync credentials from base file"""
        base_path = self.config_manager.get_base_credentials_path()
        if not base_path:
            self.logger.error("Base credentials path not configured")
            return False
        
        return self.credentials_manager.sync_credentials_from_base(Path(base_path))
    
    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a specific profile"""
        return self.credentials_manager.switch_profile(profile_name)
    
    def switch_environment(self, env_name: str) -> bool:
        """Switch to a specific environment"""
        return self.environment_manager.switch_environment(env_name)
    
    def list_profiles(self) -> Dict[str, Dict[str, str]]:
        """List all profiles"""
        return self.credentials_manager.list_profiles()
    
    def list_environments(self) -> Dict[str, Dict[str, str]]:
        """List all environments"""
        return self.environment_manager.list_environments()
    
    def save_credentials(self, profile_name: str, access_key: str, secret_key: str, session_token: str = None) -> bool:
        """Save credentials for a profile"""
        return self.credentials_manager.save_credentials(profile_name, access_key, secret_key, session_token)
    
    def save_role_profile(self, profile_name: str, role_arn: str, source_profile: str, region: str = 'us-east-1', external_id: str = None, duration_seconds: int = 3600) -> bool:
        """Save a role-based profile"""
        return self.role_manager.save_role_profile(profile_name, role_arn, source_profile, region, external_id, duration_seconds)
    
    def assume_role(self, role_arn: str, session_name: str, external_id: str = None, duration: int = 3600, profile_name: str = None, save_to_profile: bool = True, source_profile: str = None) -> Dict:
        """Assume an AWS role and optionally save credentials to a profile"""
        return self.role_manager.assume_role(role_arn, session_name, external_id, duration, profile_name, save_to_profile, source_profile)

    def remove_assume_role(self, profile_name: str = 'assumed-role') -> Dict:
        """Remove assumed role credentials from AWS credentials file"""
        return self.role_manager.remove_assume_role(profile_name)
    
    def create_assume_role_profiles_from_config(self) -> Dict[str, bool]:
        """Create assume role profiles from config.json assume_role_configs section"""
        assume_role_configs = self.config_manager.get_assume_role_configs()
        if not assume_role_configs:
            self.logger.warning("No assume_role_configs found in config.json")
            return {}
        
        return self.role_manager.create_assume_role_profiles_from_config(assume_role_configs)
    
    def generate_assume_role_script(self, config_name: str, output_file: str = '/tmp/assume-role.sh') -> Dict:
        """Generate a bash script to assume a role from config"""
        assume_role_configs = self.config_manager.get_assume_role_configs()
        
        if config_name not in assume_role_configs:
            return {
                'success': False,
                'message': f'Role configuration "{config_name}" not found in config.json'
            }
        
        config = assume_role_configs[config_name]
        return self.role_manager.generate_assume_role_script(
            role_arn=config.get('role_arn'),
            session_name=config.get('session_name', 'temp-session'),
            external_id=config.get('external_id'),
            output_file=output_file
        )
    
    def assume_role_via_script(self, config_name: str, method: str = 'script') -> Dict:
        """
        Assume a role using either script (ENV vars) or boto3 (Python client)
        
        Args:
            config_name: Name of the assume role config from config.json
            method: 'script' for ENV vars (CLI usage) or 'boto3' for Python client
            
        Returns:
            Dict with success status and instructions/credentials
        """
        assume_role_configs = self.config_manager.get_assume_role_configs()
        
        if config_name not in assume_role_configs:
            return {
                'success': False,
                'message': f'Role configuration "{config_name}" not found in config.json'
            }
        
        config = assume_role_configs[config_name]
        
        if method == 'script':
            # Actually assume role and return export commands
            return self.role_manager.assume_role_and_export(
                role_arn=config.get('role_arn'),
                session_name=config.get('session_name', 'temp-session'),
                external_id=config.get('external_id'),
                duration=config.get('duration', 3600)
            )
        elif method == 'boto3':
            # Use boto3 to assume role and save to profile
            return self.role_manager.assume_role(
                role_arn=config.get('role_arn'),
                session_name=config.get('session_name', 'temp-session'),
                external_id=config.get('external_id'),
                duration=config.get('duration', 3600),
                profile_name=config_name,
                save_to_profile=True
            )
        else:
            return {
                'success': False,
                'message': f'Invalid method: {method}. Use "script" or "boto3"'
            }
    
    def list_s3_buckets(self) -> Dict:
        """List S3 buckets"""
        return self.s3_manager.list_buckets()
    
    def list_s3_objects(self, bucket_name: str, prefix: str = '', max_keys: int = 20, continuation_token: str = None) -> Dict:
        """List S3 objects"""
        return self.s3_manager.list_objects(bucket_name, prefix, max_keys, continuation_token)
    
    def download_s3_file(self, bucket_name: str, object_key: str, local_path: str) -> Dict:
        """Download file from S3"""
        return self.s3_manager.download_file(bucket_name, object_key, local_path)
    
    def upload_s3_file(self, local_path: str, bucket_name: str, object_key: str) -> Dict:
        """Upload file to S3"""
        return self.s3_manager.upload_file(local_path, bucket_name, object_key)
    
    def delete_s3_object(self, bucket_name: str, object_key: str) -> Dict:
        """Delete S3 object"""
        return self.s3_manager.delete_object(bucket_name, object_key)

    def get_s3_credential_info(self) -> Dict:
        """Get information about current S3 credentials"""
        return self.s3_manager.get_credential_info()

    def search_s3_object_by_path(self, bucket_name: str, object_key: str) -> Dict:
        """Search for S3 object by complete path"""
        return self.s3_manager.search_object_by_path(bucket_name, object_key)

    def get_s3_presigned_download_url(self, bucket_name: str, object_key: str, expiration: int = 3600) -> Dict:
        """Generate presigned URL for S3 object download"""
        return self.s3_manager.get_presigned_download_url(bucket_name, object_key, expiration)

    def list_available_profiles(self) -> Dict:
        """List available AWS profiles and their account information"""
        return self.role_manager.list_available_profiles()

    def check_s3_bucket_access(self, bucket_name: str) -> Dict:
        """Check if an S3 bucket is accessible"""
        return self.s3_manager.check_bucket_access(bucket_name)
    
    def get_status(self) -> Dict:
        """Get current status"""
        current_profile = self.credentials_manager.get_current_profile()
        profiles = self.list_profiles()
        environments = self.list_environments()
        current_env = self.environment_manager.get_current_environment()
        
        return {
            'current_profile': current_profile,
            'current_environment': current_env,
            'profiles': profiles,
            'environments': environments,
            'base_credentials_path': self.config_manager.get_base_credentials_path()
        }
    
    def add_environment(self, env_name: str, region: str, role_arn: str, description: str = '') -> bool:
        """Add a new environment"""
        return self.environment_manager.add_environment(env_name, region, role_arn, description)
    
    def update_environment(self, env_name: str, region: str = None, role_arn: str = None, description: str = None) -> bool:
        """Update an existing environment"""
        return self.environment_manager.update_environment(env_name, region, role_arn, description)
    
    def remove_environment(self, env_name: str) -> bool:
        """Remove an environment"""
        return self.environment_manager.remove_environment(env_name)

    def clean_expired_credentials(self) -> Dict[str, Union[bool, str, int]]:
        """Clean expired temporary credentials from AWS credentials file"""
        return self.role_manager.clean_expired_credentials()
    
    def remove_profile(self, profile_name: str) -> bool:
        """Remove a profile"""
        return self.credentials_manager.remove_profile(profile_name)

    def get_credentials_status(self) -> Dict:
        """Get credentials status information"""
        try:
            base_path = Path(self.config_manager.get_base_credentials_path())
            base_file_exists = base_path.exists() if base_path else False
            
            # Check default profile
            profiles = self.credentials_manager.list_profiles()
            default_profile_valid = 'default' in profiles and 'aws_access_key_id' in profiles.get('default', {})
            
            # Check infrrd-master profile
            infrrd_master_valid = 'infrrd-master' in profiles and 'aws_access_key_id' in profiles.get('infrrd-master', {})
            
            # Check if in sync (simplified check)
            in_sync = base_file_exists and default_profile_valid
            
            # Get access keys
            base_access_key = "N/A"
            default_access_key = profiles.get('default', {}).get('aws_access_key_id', 'N/A')
            infrrd_access_key = profiles.get('infrrd-master', {}).get('aws_access_key_id', 'N/A')
            
            if base_file_exists:
                try:
                    with open(base_path, 'r') as f:
                        content = f.read()
                        # Simple extraction of access key
                        for line in content.split('\n'):
                            if 'aws_access_key_id' in line and '=' in line:
                                base_access_key = line.split('=')[1].strip()
                                break
                except:
                    pass
            
            # Check if base credentials are valid (has access key)
            base_credentials_valid = base_file_exists and base_access_key != 'N/A' and base_access_key.strip() != ''
            
            # Check if AWS credentials file exists
            aws_credentials_exists = self.credentials_manager.credentials_path.exists()
            
            return {
                'base_file_exists': base_file_exists,
                'base_credentials_valid': base_credentials_valid,
                'aws_credentials_exists': aws_credentials_exists,
                'default_profile_valid': default_profile_valid,
                'infrrd_master_valid': infrrd_master_valid,
                'in_sync': in_sync,
                'base_access_key': base_access_key,
                'default_access_key': default_access_key,
                'infrrd_access_key': infrrd_access_key
            }
            
        except Exception as e:
            self.logger.error(f"Error getting credentials status: {e}")
            return {
                'base_file_exists': False,
                'default_profile_valid': False,
                'infrrd_master_valid': False,
                'in_sync': False,
                'base_access_key': 'N/A',
                'default_access_key': 'N/A',
                'infrrd_access_key': 'N/A'
            }
