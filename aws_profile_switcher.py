#!/usr/bin/env python3
"""
AWS Profile Switcher and Credentials Manager
Simple tool to manage AWS profiles and update credentials
"""

import os
import sys
import json
import configparser
from pathlib import Path
from datetime import datetime


class AWSProfileManager:
    def __init__(self):
        self.credentials_path = Path.home() / '.aws' / 'credentials'
        self.config_path = Path.home() / '.aws' / 'config'
        self.current_profile = None
        
        # Load configuration from JSON file
        self.load_config()
        
    def load_config(self):
        """Load configuration from JSON file"""
        config_file = Path('config.json')
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                self.base_credentials_path = Path(config.get('base_credentials_path', '/home/krishnavatar/Downloads/credentials'))
                self.environments = config.get('environments', {})
                self.credentials_profiles = config.get('credentials_profiles', {})
            except Exception as e:
                print(f"Error loading config: {e}")
                self.set_default_config()
        else:
            self.set_default_config()
    
    def set_default_config(self):
        """Set default configuration"""
        self.base_credentials_path = Path('/home/krishnavatar/Downloads/credentials')
        self.environments = {
            'dev': {
                'region': 'us-west-2',
                'role_arn': 'arn:aws:iam::465825429380:role/AWS-SSO-Dev-Engineer',
                'description': 'Development Environment'
            },
            'stage': {
                'region': 'us-west-2', 
                'role_arn': 'arn:aws:iam::517080596001:role/AWS-SSO-Dev-Engineer',
                'description': 'Staging Environment'
            },
            'swbcuat': {
                'region': 'us-east-1',
                'role_arn': 'arn:aws:iam::381492214186:role/AWS-SSO-Dev-Engineer', 
                'description': 'SWBC UAT Environment'
            },
            'swbcprod': {
                'region': 'us-east-1',
                'role_arn': 'arn:aws:iam::379233983907:role/AWS-SSO-Dev-Engineer',
                'description': 'SWBC Production Environment'
            },
            'snprod': {
                'region': 'us-west-2',
                'role_arn': 'arn:aws:iam::448930163422:role/AWS-SSO-Dev-Engineer',
                'description': 'SN Production Environment'
            },
            'eu-prod': {
                'region': 'eu-west-1',
                'role_arn': 'arn:aws:iam::832828561738:role/AWS-SSO-Dev-Engineer',
                'description': 'EU Production Environment'
            }
        }
        self.credentials_profiles = {
            'default': {
                'type': 'credentials',
                'description': 'Default AWS profile'
            },
            'infrrd-master': {
                'type': 'credentials', 
                'description': 'Master credentials profile for role assumption'
            }
        }

    def sync_credentials_from_base(self):
        """Sync credentials from base file to AWS credentials file"""
        print("🔄 Syncing credentials from base file...")
        
        if not self.base_credentials_path.exists():
            print(f"❌ Base credentials file not found: {self.base_credentials_path}")
            return False
        
        try:
            # Read base credentials file
            with open(self.base_credentials_path, 'r') as f:
                base_content = f.read()
            
            # Parse the base credentials
            base_credentials = self.parse_base_credentials(base_content)
            
            if not base_credentials:
                print("❌ Could not parse credentials from base file")
                return False
            
            # Update AWS credentials file
            self.update_aws_credentials(base_credentials)
            
            print("✅ Credentials synced successfully!")
            print(f"📁 Updated: {self.credentials_path}")
            print(f"📋 Profiles updated: default, infrrd-master")
            
            return True
            
        except Exception as e:
            print(f"❌ Error syncing credentials: {e}")
            return False

    def parse_base_credentials(self, content):
        """Parse credentials from base file content"""
        credentials = {}
        
        # Try to parse as INI format first
        try:
            config = configparser.ConfigParser()
            config.read_string(content)
            
            # Look for any profile with credentials
            for section in config.sections():
                if 'aws_access_key_id' in config[section] and 'aws_secret_access_key' in config[section]:
                    credentials = {
                        'aws_access_key_id': config[section]['aws_access_key_id'],
                        'aws_secret_access_key': config[section]['aws_secret_access_key']
                    }
                    if 'aws_session_token' in config[section]:
                        credentials['aws_session_token'] = config[section]['aws_session_token']
                    break
        except:
            pass
        
        # If INI parsing failed, try to extract manually
        if not credentials:
            credentials = self.extract_credentials_manually(content)
        
        return credentials

    def extract_credentials_manually(self, content):
        """Extract credentials manually from various formats"""
        credentials = {}
        
        # Look for AWS credential patterns
        import re
        
        # Access Key ID pattern
        access_key_match = re.search(r'aws_access_key_id\s*=\s*([A-Z0-9]{20})', content)
        if access_key_match:
            credentials['aws_access_key_id'] = access_key_match.group(1)
        
        # Secret Access Key pattern
        secret_key_match = re.search(r'aws_secret_access_key\s*=\s*([A-Za-z0-9/+=]{40})', content)
        if secret_key_match:
            credentials['aws_secret_access_key'] = secret_key_match.group(1)
        
        # Session Token pattern (optional)
        session_token_match = re.search(r'aws_session_token\s*=\s*([A-Za-z0-9/+=]+)', content)
        if session_token_match:
            credentials['aws_session_token'] = session_token_match.group(1)
        
        return credentials

    def update_aws_credentials(self, credentials):
        """Update AWS credentials file with both default and infrrd-master profiles"""
        config = configparser.ConfigParser()
        
        # Read existing config if it exists
        if self.credentials_path.exists():
            config.read(self.credentials_path)
        
        # Update default profile
        if 'default' not in config:
            config['default'] = {}
        
        config['default']['aws_access_key_id'] = credentials['aws_access_key_id']
        config['default']['aws_secret_access_key'] = credentials['aws_secret_access_key']
        if 'aws_session_token' in credentials:
            config['default']['aws_session_token'] = credentials['aws_session_token']
        
        # Update infrrd-master profile
        if 'infrrd-master' not in config:
            config['infrrd-master'] = {}
        
        config['infrrd-master']['aws_access_key_id'] = credentials['aws_access_key_id']
        config['infrrd-master']['aws_secret_access_key'] = credentials['aws_secret_access_key']
        if 'aws_session_token' in credentials:
            config['infrrd-master']['aws_session_token'] = credentials['aws_session_token']
        
        # Ensure .aws directory exists
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save updated credentials
        with open(self.credentials_path, 'w') as f:
            config.write(f)

    def check_credentials_status(self):
        """Check the status of credentials in both base and AWS files"""
        print("🔍 Credentials Status Check:")
        print("-" * 50)
        
        # Check base file
        if self.base_credentials_path.exists():
            print(f"✅ Base file exists: {self.base_credentials_path}")
            try:
                with open(self.base_credentials_path, 'r') as f:
                    base_content = f.read()
                base_creds = self.parse_base_credentials(base_content)
                if base_creds:
                    print(f"🔑 Base credentials: Valid (Access Key: {base_creds['aws_access_key_id'][:10]}...)")
                else:
                    print("❌ Base credentials: Could not parse")
            except Exception as e:
                print(f"❌ Base credentials: Error reading - {e}")
        else:
            print(f"❌ Base file missing: {self.base_credentials_path}")
        
        print()
        
        # Check AWS credentials file
        if self.credentials_path.exists():
            print(f"✅ AWS credentials file exists: {self.credentials_path}")
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            # Check default profile
            if 'default' in config.sections():
                if self.is_profile_valid(config['default']):
                    print(f"✅ Default profile: Valid (Access Key: {config['default']['aws_access_key_id'][:10]}...)")
                else:
                    print("❌ Default profile: Invalid or missing credentials")
            else:
                print("❌ Default profile: Not found")
            
            # Check infrrd-master profile
            if 'infrrd-master' in config.sections():
                if self.is_profile_valid(config['infrrd-master']):
                    print(f"✅ infrrd-master profile: Valid (Access Key: {config['infrrd-master']['aws_access_key_id'][:10]}...)")
                else:
                    print("❌ infrrd-master profile: Invalid or missing credentials")
            else:
                print("❌ infrrd-master profile: Not found")
        else:
            print(f"❌ AWS credentials file missing: {self.credentials_path}")
        
        print()
        
        # Check sync status
        if (self.base_credentials_path.exists() and self.credentials_path.exists()):
            try:
                with open(self.base_credentials_path, 'r') as f:
                    base_content = f.read()
                base_creds = self.parse_base_credentials(base_content)
                
                if base_creds:
                    config = configparser.ConfigParser()
                    config.read(self.credentials_path)
                    
                    if ('default' in config.sections() and 'infrrd-master' in config.sections() and
                        self.is_profile_valid(config['default']) and self.is_profile_valid(config['infrrd-master'])):
                        
                        if (config['default']['aws_access_key_id'] == base_creds['aws_access_key_id'] and
                            config['infrrd-master']['aws_access_key_id'] == base_creds['aws_access_key_id']):
                            print("✅ Sync status: All credentials are in sync")
                        else:
                            print("⚠️ Sync status: Credentials are out of sync")
                    else:
                        print("⚠️ Sync status: Cannot check - missing or invalid profiles")
                else:
                    print("⚠️ Sync status: Cannot check - base credentials invalid")
            except Exception as e:
                print(f"⚠️ Sync status: Error checking - {e}")

    def is_profile_valid(self, profile_config):
        """Check if a profile configuration is valid"""
        required_keys = ['aws_access_key_id', 'aws_secret_access_key']
        return all(key in profile_config for key in required_keys)

    def switch_profile(self, profile_name):
        """Switch to a specific AWS profile"""
        print(f"🔄 Switching to profile: {profile_name}")
        
        # Set environment variable
        os.environ['AWS_PROFILE'] = profile_name
        self.current_profile = profile_name
        
        print(f"✅ Switched to profile: {profile_name}")
        return True

    def switch_environment(self, env_name):
        """Switch to a specific environment"""
        print(f"🔄 Switching to {env_name.upper()} environment...")
        
        if env_name not in self.environments:
            print(f"❌ Environment '{env_name}' not found")
            return False
        
        env_config = self.environments[env_name]
        
        try:
            # Update AWS config file
            config = configparser.ConfigParser()
            
            # Read existing config if it exists
            if self.config_path.exists():
                config.read(self.config_path)
            
            # Update default profile configuration
            if 'profile default' not in config:
                config['profile default'] = {}
            
            config['profile default']['role_arn'] = env_config['role_arn']
            config['profile default']['region'] = env_config['region']
            config['profile default']['source_profile'] = 'infrrd-master'
            
            # Ensure .aws directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save updated config
            with open(self.config_path, 'w') as f:
                config.write(f)
            
            print(f"✅ Switched to {env_name.upper()} environment")
            print(f"📍 Region: {env_config['region']}")
            print(f"🔗 Role ARN: {env_config['role_arn']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error switching environment: {e}")
            return False

    def save_credentials(self, profile_name, access_key, secret_key, session_token=''):
        """Save credentials for a specific profile"""
        print(f"💾 Saving credentials for profile: {profile_name}")
        
        try:
            config = configparser.ConfigParser()
            
            # Read existing config if it exists
            if self.credentials_path.exists():
                config.read(self.credentials_path)
            
            # Update or create profile
            if profile_name not in config:
                config[profile_name] = {}
            
            config[profile_name]['aws_access_key_id'] = access_key
            config[profile_name]['aws_secret_access_key'] = secret_key
            
            if session_token:
                config[profile_name]['aws_session_token'] = session_token
            
            # Ensure .aws directory exists
            self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save updated credentials
            with open(self.credentials_path, 'w') as f:
                config.write(f)
            
            print(f"✅ Credentials saved for profile: {profile_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving credentials: {e}")
            return False

    def save_role_profile(self, profile_name, source_profile, role_arn, region='', duration='3600'):
        """Save a role-based profile configuration"""
        print(f"💾 Saving role profile: {profile_name}")
        
        try:
            config = configparser.ConfigParser()
            
            # Read existing config if it exists
            if self.config_path.exists():
                config.read(self.config_path)
            
            # Create profile section
            profile_section = f'profile {profile_name}'
            if profile_section not in config:
                config[profile_section] = {}
            
            config[profile_section]['role_arn'] = role_arn
            config[profile_section]['source_profile'] = source_profile
            
            if region:
                config[profile_section]['region'] = region
            
            if duration:
                config[profile_section]['duration_seconds'] = duration
            
            # Ensure .aws directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save updated config
            with open(self.config_path, 'w') as f:
                config.write(f)
            
            print(f"✅ Role profile saved: {profile_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving role profile: {e}")
            return False

    def remove_profile(self, profile_name):
        """Remove a profile from credentials file"""
        print(f"🗑️ Removing profile: {profile_name}")
        
        try:
            if not self.credentials_path.exists():
                print(f"❌ Credentials file not found: {self.credentials_path}")
                return False
            
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            if profile_name in config.sections():
                config.remove_section(profile_name)
                
                # Save updated config
                with open(self.credentials_path, 'w') as f:
                    config.write(f)
                
                print(f"✅ Profile removed: {profile_name}")
                return True
            else:
                print(f"❌ Profile not found: {profile_name}")
                return False
                
        except Exception as e:
            print(f"❌ Error removing profile: {e}")
            return False

    def remove_role_profile(self, profile_name):
        """Remove a role profile from config file"""
        print(f"🗑️ Removing role profile: {profile_name}")
        
        try:
            if not self.config_path.exists():
                print(f"❌ Config file not found: {self.config_path}")
                return False
            
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            profile_section = f'profile {profile_name}'
            if profile_section in config.sections():
                config.remove_section(profile_section)
                
                # Save updated config
                with open(self.config_path, 'w') as f:
                    config.write(f)
                
                print(f"✅ Role profile removed: {profile_name}")
                return True
            else:
                print(f"❌ Role profile not found: {profile_name}")
                return False
                
        except Exception as e:
            print(f"❌ Error removing role profile: {e}")
            return False

    def force_refresh_credentials(self):
        """Force refresh credentials by re-syncing from base file"""
        print("🔄 Force refreshing credentials...")
        return self.sync_credentials_from_base()

    def clean_config_file(self):
        """Clean up the config file by removing invalid entries"""
        print("🧹 Cleaning config file...")
        
        try:
            if not self.config_path.exists():
                print(f"❌ Config file not found: {self.config_path}")
                return False
            
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            # Remove sections that don't start with 'profile '
            sections_to_remove = []
            for section in config.sections():
                if not section.startswith('profile '):
                    sections_to_remove.append(section)
            
            for section in sections_to_remove:
                config.remove_section(section)
                print(f"🗑️ Removed invalid section: {section}")
            
            # Save cleaned config
            with open(self.config_path, 'w') as f:
                config.write(f)
            
            print("✅ Config file cleaned successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning config file: {e}")
            return False

    def force_clean_and_reset(self):
        """Force clean and reset to default configuration"""
        print("🔄 Force cleaning and resetting...")
        
        try:
            # Clean config file
            self.clean_config_file()
            
            # Reset to default environment
            if 'dev' in self.environments:
                self.switch_environment('dev')
                print("✅ Reset to default environment: DEV")
            
            print("✅ Force clean and reset completed")
            
        except Exception as e:
            print(f"❌ Error during force clean and reset: {e}")

    def list_profiles(self):
        """List all available profiles"""
        print("📋 Available Profiles:")
        print("-" * 30)
        
        # List credentials profiles
        if self.credentials_path.exists():
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            for profile in config.sections():
                status = "✅ Valid" if self.is_profile_valid(config[profile]) else "❌ Invalid"
                print(f"🔑 {profile}: {status}")
        
        # List role profiles
        if self.config_path.exists():
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            for profile in config.sections():
                if profile.startswith('profile '):
                    profile_name = profile.replace('profile ', '')
                    print(f"🏷️ {profile_name}: Role-based profile")

    def list_environments(self):
        """List all available environments"""
        print("🌍 Available Environments:")
        print("-" * 30)
        
        # Region display mapping for better user understanding
        region_display = {
            'us-east-1': 'US East 1 (N. Virginia)',
            'us-east-2': 'US East 2 (Ohio)', 
            'us-west-1': 'US West 1 (N. California)',
            'us-west-2': 'US West 2 (Oregon)',
            'eu-west-1': 'Europe West 1 (Ireland)',
            'eu-west-2': 'Europe West 2 (London)',
            'eu-west-3': 'Europe West 3 (Paris)',
            'eu-central-1': 'Europe Central 1 (Frankfurt)',
            'ap-southeast-1': 'Asia Pacific Southeast 1 (Singapore)',
            'ap-southeast-2': 'Asia Pacific Southeast 2 (Sydney)',
            'ap-northeast-1': 'Asia Pacific Northeast 1 (Tokyo)',
            'ap-northeast-2': 'Asia Pacific Northeast 2 (Seoul)',
            'ap-south-1': 'Asia Pacific South 1 (Mumbai)',
            'ca-central-1': 'Canada Central 1 (Central)',
            'sa-east-1': 'South America East 1 (São Paulo)'
        }
        
        for env_name, env_config in self.environments.items():
            region_code = env_config['region']
            region_display_name = region_display.get(region_code, region_code)
            print(f"🌐 {env_name.upper()}: {env_config['description']}")
            print(f"   Region: {region_code} ({region_display_name})")
            print(f"   Role: {env_config['role_arn']}")
            print()


def main():
    """Main function for command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python aws_profile_switcher.py <command> [options]")
        print("\nCommands:")
        print("  sync                    - Sync credentials from base file")
        print("  status                  - Check credentials status")
        print("  switch-profile <name>   - Switch to a specific profile")
        print("  switch-env <name>       - Switch to a specific environment")
        print("  save-creds <name>       - Save credentials for a profile")
        print("  save-role <name>        - Save a role-based profile")
        print("  remove-profile <name>   - Remove a profile")
        print("  remove-role <name>      - Remove a role profile")
        print("  list-profiles           - List all profiles")
        print("  list-envs               - List all environments")
        print("  clean                   - Clean config file")
        print("  reset                   - Force clean and reset")
        return
    
    manager = AWSProfileManager()
    command = sys.argv[1].lower()
    
    match command:
        case 'sync':
            manager.sync_credentials_from_base()
        case 'status':
            manager.check_credentials_status()
        case 'switch-profile':
            if len(sys.argv) < 3:
                print("❌ Profile name required")
                return
            manager.switch_profile(sys.argv[2])
        case 'switch-env':
            if len(sys.argv) < 3:
                print("❌ Environment name required")
                return
            manager.switch_environment(sys.argv[2])
        case 'save-creds':
            if len(sys.argv) < 3:
                print("❌ Profile name required")
                return
            profile_name = sys.argv[2]
            access_key = input("Enter AWS Access Key ID: ")
            secret_key = input("Enter AWS Secret Access Key: ")
            session_token = input("Enter AWS Session Token (optional): ")
            manager.save_credentials(profile_name, access_key, secret_key, session_token)
        case 'save-role':
            if len(sys.argv) < 3:
                print("❌ Profile name required")
                return
            profile_name = sys.argv[2]
            source_profile = input("Enter source profile: ")
            role_arn = input("Enter role ARN: ")
            region = input("Enter region (optional): ")
            duration = input("Enter duration in seconds (default 3600): ") or "3600"
            manager.save_role_profile(profile_name, source_profile, role_arn, region, duration)
        case 'remove-profile':
            if len(sys.argv) < 3:
                print("❌ Profile name required")
                return
            manager.remove_profile(sys.argv[2])
        case 'remove-role':
            if len(sys.argv) < 3:
                print("❌ Profile name required")
                return
            manager.remove_role_profile(sys.argv[2])
        case 'list-profiles':
            manager.list_profiles()
        case 'list-envs':
            manager.list_environments()
        case 'clean':
            manager.clean_config_file()
        case 'reset':
            manager.force_clean_and_reset()
        case _:
            print(f"❌ Unknown command: {command}")


if __name__ == '__main__':
    main()
