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

    def _get_credentials_from_file(self, profile_name: str) -> Optional[Dict[str, str]]:
        """Read credentials directly from the credentials file"""
        try:
            if not self.credentials_path.exists():
                return None

            config = configparser.ConfigParser()
            config.read(self.credentials_path)

            if profile_name not in config.sections():
                return None

            section = config[profile_name]
            if 'aws_access_key_id' in section and 'aws_secret_access_key' in section:
                creds = {
                    'aws_access_key_id': section['aws_access_key_id'],
                    'aws_secret_access_key': section['aws_secret_access_key']
                }
                if 'aws_session_token' in section:
                    creds['aws_session_token'] = section['aws_session_token']

                    # Check if session token is expired
                    try:
                        test_client = boto3.client('sts',
                                                 aws_access_key_id=creds['aws_access_key_id'],
                                                 aws_secret_access_key=creds['aws_secret_access_key'],
                                                 aws_session_token=creds['aws_session_token'],
                                                 region_name='us-east-1')
                        # Try to get caller identity - this will fail if token is expired
                        test_client.get_caller_identity()
                    except Exception as e:
                        if 'ExpiredToken' in str(e) or 'expired' in str(e).lower():
                            self.logger.warning(f"Profile '{profile_name}' contains expired temporary credentials, skipping")
                            return None
                        # For other errors, continue - might be temporary network issues

                # Log the credentials being used (first 10 chars for security)
                self.logger.info(f"Using credentials for {profile_name}: {creds['aws_access_key_id'][:10]}...")
                return creds

            return None

        except Exception as e:
            self.logger.error(f"Error reading credentials from file: {e}")
            return None
    
    def _create_sts_client(self, profile_name: str = None) -> Optional[object]:
        """Create STS client with proper credential isolation"""
        import os

        # Store current environment variables
        old_env = {}
        aws_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_PROFILE']
        for var in aws_env_vars:
            if var in os.environ:
                old_env[var] = os.environ[var]
                del os.environ[var]

        try:
            # Determine which profile to use
            if profile_name:
                profile_to_use = profile_name
            else:
                # Check config for preferred base profile
                from aws_profile_manager.core.config import ConfigManager
                config_manager = ConfigManager()
                config = config_manager.config
                preferred_profile = config.get('base_profile', 'default')

                # Try preferred profile first, then others
                profiles_to_try = [preferred_profile]
                if preferred_profile != 'default':
                    profiles_to_try.append('default')
                if preferred_profile != 'infrrd-master':
                    profiles_to_try.append('infrrd-master')

                profile_to_use = None

                for profile in profiles_to_try:
                    try:
                        # Test if profile exists and works
                        test_session = boto3.Session(profile_name=profile)
                        test_sts = test_session.client('sts', region_name='us-east-1')
                        identity = test_sts.get_caller_identity()
                        account_id = identity.get('Account')

                        # Check if this is a base account (not SSO temporary credentials)
                        # SSO accounts typically have different account IDs than the base accounts
                        expected_accounts = ['379233983907', '465825429380', '517080596001', '381492214186', '448930163422', '832828561738']
                        if account_id in expected_accounts:
                            profile_to_use = profile
                            self.logger.info(f"Using base profile '{profile}' with account: {account_id}")
                            break
                        else:
                            self.logger.info(f"Profile '{profile}' uses account {account_id} (may be SSO), trying next profile")
                    except Exception as e:
                        self.logger.debug(f"Profile '{profile}' not available or invalid: {e}")
                        continue

                if not profile_to_use:
                    # Fall back to default if no preferred profile works
                    profile_to_use = 'default'
                    self.logger.warning("No preferred base profile found, using 'default'")

            # Create STS client using the determined profile
            sts_client = boto3.Session(profile_name=profile_to_use).client('sts', region_name='us-east-1')

            # Verify credentials
            try:
                identity = sts_client.get_caller_identity()
                self.logger.info(f"STS client using account: {identity.get('Account')}, user: {identity.get('UserId')}, profile: {profile_to_use}")
            except Exception as e:
                self.logger.warning(f"Could not get caller identity for STS: {e}")

            return sts_client

        except Exception as e:
            self.logger.error(f"Failed to create STS client: {e}")
            return None
        finally:
            # Restore original environment variables
            for var, value in old_env.items():
                os.environ[var] = value
    
    def assume_role(self, role_arn: str, session_name: str, external_id: Optional[str] = None,
                   duration: int = 3600, profile_name: str = None, save_to_profile: bool = True, source_profile: str = None) -> Dict[str, Union[bool, str, Dict]]:
        """
        Assume an AWS role and get temporary credentials

        Args:
            role_arn: The ARN of the role to assume
            session_name: Name for the role session
            external_id: Optional external ID for the role assumption
            duration: Duration in seconds for the credentials (default: 3600)
            profile_name: Profile name to save credentials to (default: 'assumed-role')
            save_to_profile: Whether to save credentials to AWS credentials file (default: True)
            source_profile: Profile name to use for assuming the role (default: auto-detect)
        """
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            # Create STS client with proper credential isolation
            sts_client = self._create_sts_client(source_profile)
            if not sts_client:
                return {
                    'success': False,
                    'message': 'Failed to load base credentials. Please ensure your credentials file is properly configured.'
                }

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
            
            # Save credentials to profile if requested
            if save_to_profile:
                if not profile_name:
                    profile_name = 'assumed-role'
                
                self._save_assumed_credentials(
                    profile_name,
                    credentials['AccessKeyId'],
                    credentials['SecretAccessKey'],
                    credentials['SessionToken']
                )
                self.logger.info(f"Credentials saved to profile: {profile_name}")
            
            return {
                'success': True,
                'message': f'Role assumed successfully. Credentials saved to profile: {profile_name}' if save_to_profile else 'Role assumed successfully',
                'profile_name': profile_name if save_to_profile else None,
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

    def list_available_profiles(self) -> Dict[str, Dict[str, str]]:
        """List available AWS profiles and their account information"""
        profiles_info = {}

        try:
            # Check both credentials file and config file
            credentials_path = Path.home() / '.aws' / 'credentials'

            profiles_to_check = []

            # Get profiles from credentials file
            if credentials_path.exists():
                import configparser
                cred_config = configparser.ConfigParser()
                cred_config.read(credentials_path)
                profiles_to_check.extend(cred_config.sections())

            # Add default if not already there
            if 'default' not in profiles_to_check:
                profiles_to_check.append('default')

            for profile_name in profiles_to_check:
                try:
                    # Test the profile
                    session = boto3.Session(profile_name=profile_name)
                    sts_client = session.client('sts', region_name='us-east-1')
                    identity = sts_client.get_caller_identity()

                    profiles_info[profile_name] = {
                        'account_id': identity.get('Account'),
                        'user_id': identity.get('UserId'),
                        'arn': identity.get('Arn'),
                        'available': True,
                        'error': None
                    }

                except Exception as e:
                    profiles_info[profile_name] = {
                        'account_id': None,
                        'user_id': None,
                        'arn': None,
                        'available': False,
                        'error': str(e)
                    }

        except Exception as e:
            self.logger.error(f"Error listing profiles: {e}")

        return profiles_info
    
    def _save_assumed_credentials(self, profile_name: str, access_key: str, secret_key: str, session_token: str) -> bool:
        """Save assumed role credentials to AWS credentials file"""
        try:
            # Create .aws directory if it doesn't exist
            self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing credentials
            config = configparser.ConfigParser()
            if self.credentials_path.exists():
                config.read(self.credentials_path)
            
            # Create or update profile section
            if not config.has_section(profile_name):
                config.add_section(profile_name)
            
            config.set(profile_name, 'aws_access_key_id', access_key)
            config.set(profile_name, 'aws_secret_access_key', secret_key)
            config.set(profile_name, 'aws_session_token', session_token)
            
            # Write to file
            with open(self.credentials_path, 'w') as f:
                config.write(f)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save assumed credentials: {e}")
            return False
    
    def save_role_profile(self, profile_name: str, role_arn: str, source_profile: str, region: str = 'us-east-1', 
                         external_id: Optional[str] = None, duration_seconds: int = 3600) -> bool:
        """
        Save a role-based profile to AWS config

        This creates a profile that AWS CLI will automatically use to assume the role.
        This is the recommended approach for roles with external_id.

        Args:
            profile_name: Name for the profile
            role_arn: ARN of the role to assume
            source_profile: Profile with credentials to use for assuming the role
            region: AWS region for the profile
            external_id: External ID for role assumption (if required)
            duration_seconds: Duration for assumed role credentials
        """
        try:
            # Create .aws directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Read existing config
            config = configparser.ConfigParser()
            if self.config_path.exists():
                config.read(self.config_path)

            # Create the profile section name
            section_name = f'profile {profile_name}' if profile_name != 'default' else 'default'
            
            if not config.has_section(section_name):
                config.add_section(section_name)

            config.set(section_name, 'role_arn', role_arn)
            config.set(section_name, 'source_profile', source_profile)
            config.set(section_name, 'region', region)
            config.set(section_name, 'duration_seconds', str(duration_seconds))

            if external_id:
                config.set(section_name, 'external_id', external_id)

            # Write to file
            with open(self.config_path, 'w') as f:
                config.write(f)

            self.logger.info(f"Role profile saved: {profile_name}")
            self.logger.info(f"  Role ARN: {role_arn}")
            self.logger.info(f"  Source Profile: {source_profile}")
            self.logger.info(f"  Region: {region}")
            if external_id:
                self.logger.info(f"  External ID: {external_id[:20]}...")
            self.logger.info(f"Usage: aws --profile {profile_name} s3 ls")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save role profile: {e}")
            return False
    
    def assume_role_and_export(self, role_arn: str, session_name: str, external_id: Optional[str] = None,
                              duration: int = 3600, source_profile: str = None) -> Dict[str, Union[bool, str]]:
        """
        Assume role and return export commands for setting ENV variables
        
        This actually performs the assume role operation and returns the commands
        that the user needs to copy-paste into their terminal.
        
        Args:
            role_arn: The ARN of the role to assume
            session_name: Name for the role session
            external_id: Optional external ID for the role assumption
            duration: Duration in seconds for the credentials
            
        Returns:
            Dict with success status and export commands
        """
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            # Create STS client with proper credential isolation
            sts_client = self._create_sts_client(source_profile)
            if not sts_client:
                return {
                    'success': False,
                    'message': 'Failed to load base credentials. Please ensure your credentials file is properly configured.'
                }
            
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
            
            # Generate export commands
            export_commands = f"""export AWS_ACCESS_KEY_ID={credentials['AccessKeyId']}
export AWS_SECRET_ACCESS_KEY={credentials['SecretAccessKey']}
export AWS_SESSION_TOKEN={credentials['SessionToken']}"""
            
            return {
                'success': True,
                'message': 'Role assumed successfully',
                'credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration'].isoformat()
                },
                'export_commands': export_commands,
                'instructions': 'Copy and paste these commands into your terminal'
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

    def list_available_profiles(self) -> Dict[str, Dict[str, str]]:
        """List available AWS profiles and their account information"""
        profiles_info = {}

        try:
            # Check both credentials file and config file
            credentials_path = Path.home() / '.aws' / 'credentials'

            profiles_to_check = []

            # Get profiles from credentials file
            if credentials_path.exists():
                import configparser
                cred_config = configparser.ConfigParser()
                cred_config.read(credentials_path)
                profiles_to_check.extend(cred_config.sections())

            # Add default if not already there
            if 'default' not in profiles_to_check:
                profiles_to_check.append('default')

            for profile_name in profiles_to_check:
                try:
                    # Test the profile
                    session = boto3.Session(profile_name=profile_name)
                    sts_client = session.client('sts', region_name='us-east-1')
                    identity = sts_client.get_caller_identity()

                    profiles_info[profile_name] = {
                        'account_id': identity.get('Account'),
                        'user_id': identity.get('UserId'),
                        'arn': identity.get('Arn'),
                        'available': True,
                        'error': None
                    }

                except Exception as e:
                    profiles_info[profile_name] = {
                        'account_id': None,
                        'user_id': None,
                        'arn': None,
                        'available': False,
                        'error': str(e)
                    }

        except Exception as e:
            self.logger.error(f"Error listing profiles: {e}")

        return profiles_info
    
    def assume_role_via_script(self, role_arn: str, session_name: str, external_id: Optional[str] = None, 
                              cleanup: bool = True) -> Dict[str, Union[bool, str]]:
        """
        Generate and execute a bash script to assume role and set environment variables
        
        This creates a temporary script, executes it, and provides instructions for sourcing it.
        The script sets AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN as env vars.
        
        Args:
            role_arn: The ARN of the role to assume
            session_name: Name for the role session
            external_id: Optional external ID for the role assumption
            cleanup: Whether to delete the script after showing instructions (default: True)
            
        Returns:
            Dict with success status, script path, and sourcing instructions
        """
        import tempfile
        import os
        
        try:
            # Create temporary script file
            fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='assume-role-', text=True)
            
            script_content = f"""#!/bin/bash

# Clear previously assumed role credentials if they exist
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo "Previous AWS credentials cleared."

# Assume the role and get temporary credentials
echo "Assuming role..."

response=$(aws sts assume-role \\
  --role-arn {role_arn} \\
  --role-session-name {session_name}"""
            
            if external_id:
                script_content += f""" \\
  --external-id {external_id}"""
            
            script_content += """ 2>&1)

# Check if assume-role was successful
if [ $? -ne 0 ]; then
  echo "❌ Failed to assume role"
  echo "$response"
  exit 1
fi

# Parse and export credentials using jq
export AWS_ACCESS_KEY_ID=$(echo "$response" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$response" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$response" | jq -r '.Credentials.SessionToken')

echo "✅ Temporary AWS credentials have been set."
echo "📌 You can now use: aws s3 ls"
echo "⏰ Credentials will expire in 1 hour"
"""
            
            # Write the script
            with os.fdopen(fd, 'w') as f:
                f.write(script_content)
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            self.logger.info(f"Generated temporary assume role script: {script_path}")
            
            return {
                'success': True,
                'script_path': script_path,
                'message': 'Script generated successfully',
                'instructions': f"""
╔══════════════════════════════════════════════════════════════╗
║  Run this command in your terminal to set AWS credentials:  ║
╚══════════════════════════════════════════════════════════════╝

    source {script_path}

    OR

    . {script_path}

⚠️  IMPORTANT: You must run 'source' in your TERMINAL, not here!

After sourcing, you can use AWS CLI directly:
    aws s3 ls
    aws s3 cp file.txt s3://bucket/
""",
                'cleanup': cleanup
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate script: {e}")
            return {
                'success': False,
                'message': f'Error generating script: {str(e)}'
            }
    
    def generate_assume_role_script(self, role_arn: str, session_name: str, external_id: Optional[str] = None, 
                                   output_file: str = '/tmp/assume-role.sh') -> Dict[str, Union[bool, str]]:
        """
        Generate a bash script to assume role and export credentials as environment variables
        This mimics the behavior of your working bash scripts.
        
        Args:
            role_arn: The ARN of the role to assume
            session_name: Name for the role session
            external_id: Optional external ID for the role assumption
            output_file: Path where to save the script (default: /tmp/assume-role.sh)
            
        Returns:
            Dict with success status, script path, and instructions
        """
        try:
            script_content = f"""#!/bin/bash

# Clear previously assumed role credentials if they exist
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo "Previous AWS credentials cleared."

# Assume the role and get temporary credentials
echo "Assuming role: {role_arn}..."

response=$(aws sts assume-role \\
  --role-arn {role_arn} \\
  --role-session-name {session_name}"""
            
            if external_id:
                script_content += f""" \\
  --external-id {external_id}"""
            
            script_content += """)

# Check if assume-role was successful
if [ $? -ne 0 ]; then
  echo "Failed to assume role"
  exit 1
fi

# Parse and export credentials using jq
export AWS_ACCESS_KEY_ID=$(echo "$response" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$response" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$response" | jq -r '.Credentials.SessionToken')

echo "✅ Temporary AWS credentials have been set."
echo "📌 You can now use: aws s3 ls"
echo "⏰ Credentials will expire in 1 hour"
"""
            
            # Write the script
            from pathlib import Path
            script_path = Path(output_file)
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            self.logger.info(f"Generated assume role script: {output_file}")
            
            return {
                'success': True,
                'script_path': str(script_path),
                'message': f'Script generated at {output_file}',
                'instructions': f'Run this in your terminal:\n  source {output_file}\n  # OR\n  . {output_file}'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate script: {e}")
            return {
                'success': False,
                'message': f'Error generating script: {str(e)}'
            }
    
    def create_assume_role_profiles_from_config(self, config_data: Dict) -> Dict[str, bool]:
        """
        Create assume role profiles from configuration data
        
        Args:
            config_data: Dictionary with role configurations
            
        Returns:
            Dictionary mapping profile names to success status
        """
        results = {}
        
        for profile_name, role_config in config_data.items():
            try:
                success = self.save_role_profile(
                    profile_name=profile_name,
                    role_arn=role_config.get('role_arn'),
                    source_profile=role_config.get('source_profile', 'infrrd-master'),
                    region=role_config.get('region', 'us-east-1'),
                    external_id=role_config.get('external_id'),
                    duration_seconds=role_config.get('duration', 3600)
                )
                results[profile_name] = success
            except Exception as e:
                self.logger.error(f"Failed to create profile {profile_name}: {e}")
                results[profile_name] = False
        
        return results
    
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
                    profile_data = dict(config[section])
                    if 'role_arn' in profile_data:  # Only include role-based profiles
                        role_profiles[profile_name] = profile_data
                elif section == 'default':
                    profile_data = dict(config[section])
                    if 'role_arn' in profile_data:  # Only include role-based profiles
                        role_profiles['default'] = profile_data
            
        except Exception as e:
            self.logger.error(f"Failed to list role profiles: {e}")
        
        return role_profiles
    
    def remove_role_profile(self, profile_name: str) -> bool:
        """Remove a role-based profile"""
        try:
            if not self.config_path.exists():
                return False

            config = configparser.ConfigParser()
            config.read(self.config_path)

            section_name = f'profile {profile_name}' if profile_name != 'default' else 'default'

            if config.has_section(section_name):
                config.remove_section(section_name)

                with open(self.config_path, 'w') as f:
                    config.write(f)

                self.logger.info(f"Removed role profile: {profile_name}")
                return True
            else:
                self.logger.warning(f"Profile not found: {profile_name}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to remove role profile {profile_name}: {e}")
            return False

    def clean_expired_credentials(self) -> Dict[str, Union[bool, str, int]]:
        """Clean expired temporary credentials from AWS credentials file"""
        try:
            if not self.credentials_path.exists():
                return {
                    'success': False,
                    'message': 'Credentials file does not exist'
                }

            config = configparser.ConfigParser()
            config.read(self.credentials_path)

            expired_profiles = []
            for profile_name in config.sections():
                section = config[profile_name]
                if 'aws_session_token' in section and 'aws_access_key_id' in section and 'aws_secret_access_key' in section:
                    # This looks like temporary credentials, check if expired
                    try:
                        test_client = boto3.client('sts',
                                                 aws_access_key_id=section['aws_access_key_id'],
                                                 aws_secret_access_key=section['aws_secret_access_key'],
                                                 aws_session_token=section['aws_session_token'],
                                                 region_name='us-east-1')
                        # Try to get caller identity - this will fail if token is expired
                        test_client.get_caller_identity()
                        self.logger.debug(f"Profile '{profile_name}' credentials are still valid")
                    except Exception as e:
                        if 'ExpiredToken' in str(e) or 'expired' in str(e).lower():
                            expired_profiles.append(profile_name)
                            self.logger.info(f"Found expired credentials in profile: {profile_name}")
                        else:
                            self.logger.debug(f"Profile '{profile_name}' has session token but other error: {e}")

            # Remove expired profiles
            for profile_name in expired_profiles:
                config.remove_section(profile_name)
                self.logger.info(f"Removed expired profile: {profile_name}")

            # Save the cleaned file
            with open(self.credentials_path, 'w') as f:
                config.write(f)

            return {
                'success': True,
                'message': f'Cleaned {len(expired_profiles)} expired credential profiles',
                'cleaned_count': len(expired_profiles)
            }

        except Exception as e:
            self.logger.error(f"Error cleaning expired credentials: {e}")
            return {
                'success': False,
                'message': f'Error cleaning credentials: {str(e)}'
            }

    def remove_assume_role(self, profile_name: str = 'assumed-role') -> Dict[str, Union[bool, str]]:
        """
        Remove assumed role credentials from AWS credentials file

        Args:
            profile_name: Profile name to remove credentials from (default: 'assumed-role')

        Returns:
            Dict with success status and message
        """
        try:
            if not self.credentials_path.exists():
                return {
                    'success': False,
                    'message': 'Credentials file does not exist'
                }

            config = configparser.ConfigParser()
            config.read(self.credentials_path)

            if not config.has_section(profile_name):
                return {
                    'success': False,
                    'message': f'Assumed role profile "{profile_name}" not found'
                }

            # Check if this looks like assumed role credentials
            section = config[profile_name]
            has_session_token = 'aws_session_token' in section

            if not has_session_token:
                return {
                    'success': False,
                    'message': f'Profile "{profile_name}" does not appear to be an assumed role (no session token found)'
                }

            # Remove the section
            config.remove_section(profile_name)

            # Write back to file
            with open(self.credentials_path, 'w') as f:
                config.write(f)

            self.logger.info(f"Removed assumed role credentials for profile: {profile_name}")

            return {
                'success': True,
                'message': f'Assumed role credentials removed for profile: {profile_name}'
            }

        except Exception as e:
            self.logger.error(f"Failed to remove assumed role for {profile_name}: {e}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def list_available_profiles(self) -> Dict[str, Dict[str, str]]:
        """List available AWS profiles and their account information"""
        profiles_info = {}

        try:
            # Check credentials file
            credentials_path = Path.home() / '.aws' / 'credentials'

            profiles_to_check = []

            # Get profiles from credentials file
            if credentials_path.exists():
                import configparser
                cred_config = configparser.ConfigParser()
                cred_config.read(credentials_path)
                profiles_to_check.extend(cred_config.sections())

            # Add default if not already there
            if 'default' not in profiles_to_check:
                profiles_to_check.append('default')

            for profile_name in profiles_to_check:
                try:
                    # Test the profile
                    session = boto3.Session(profile_name=profile_name)
                    sts_client = session.client('sts', region_name='us-east-1')
                    identity = sts_client.get_caller_identity()

                    profiles_info[profile_name] = {
                        'account_id': identity.get('Account'),
                        'user_id': identity.get('UserId'),
                        'arn': identity.get('Arn'),
                        'available': True,
                        'error': None
                    }

                except Exception as e:
                    profiles_info[profile_name] = {
                        'account_id': None,
                        'user_id': None,
                        'arn': None,
                        'available': False,
                        'error': str(e)
                    }

        except Exception as e:
            self.logger.error(f"Error listing profiles: {e}")

        return profiles_info
