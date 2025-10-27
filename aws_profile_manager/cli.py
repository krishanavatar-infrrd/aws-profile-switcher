#!/usr/bin/env python3
"""
Command Line Interface for AWS Profile Manager
"""

import sys
from typing import List

from aws_profile_manager.core.manager import AWSProfileManager
from aws_profile_manager.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def print_usage():
    """Print usage information"""
    print("Usage: python -m aws_profile_manager.cli <command> [options]")
    print("\nCommands:")
    print("  sync                    - Sync credentials from base file")
    print("  status                  - Check credentials status")
    print("  switch-profile <name>   - Switch to a specific profile")
    print("  switch-env <name>       - Switch to a specific environment")
    print("  save-creds <name>       - Save credentials for a profile")
    print("  save-role <name>        - Save a role-based profile")
    print("  assume-role <arn>       - Assume an AWS role and save to profile")
    print("  setup-assume-roles      - Create all assume role profiles from config")
    print("  use-role <name> [method] - Assume role (method: script|boto3, default: script)")
    print("  list-profiles           - List all profiles")
    print("  list-environments       - List all environments")
    print("  list-buckets            - List S3 buckets")
    print("  list-s3 <bucket>        - List S3 objects in bucket")
    print("  download <bucket> <key> - Download S3 object")
    print("  upload <file> <bucket>  - Upload file to S3")
    print("  remove-profile <name>   - Remove a profile")
    print("  remove-env <name>       - Remove an environment")
    print("  env-vars                - Show current AWS environment variables")
    print("  clean-creds             - Clean expired credentials from AWS credentials file")


def main():
    """Main CLI function"""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1]
    manager = AWSProfileManager()
    
    try:
        match command:
            case 'sync':
                if manager.sync_credentials():
                    print("✅ Credentials synced successfully")
                else:
                    print("❌ Failed to sync credentials")
            
            case 'status':
                status = manager.get_status()
                print(f"Current Profile: {status['current_profile']}")
                print(f"Current Environment: {status['current_environment']}")
                print(f"Base Credentials Path: {status['base_credentials_path']}")
            
            case 'switch-profile':
                if len(sys.argv) < 3:
                    print("❌ Profile name required")
                    return
                profile_name = sys.argv[2]
                if manager.switch_profile(profile_name):
                    print(f"✅ Switched to profile: {profile_name}")
                else:
                    print(f"❌ Failed to switch to profile: {profile_name}")
            
            case 'switch-env':
                if len(sys.argv) < 3:
                    print("❌ Environment name required")
                    return
                env_name = sys.argv[2]
                if manager.switch_environment(env_name):
                    print(f"✅ Switched to environment: {env_name}")
                else:
                    print(f"❌ Failed to switch to environment: {env_name}")
            
            case 'list-profiles':
                profiles = manager.list_available_profiles()
                print("📋 Available AWS Profiles:")
                print("=" * 60)
                for name, info in profiles.items():
                    status = "✅ Available" if info['available'] else "❌ Not Available"
                    account = info.get('account_id', 'N/A')
                    print(f"Profile: {name}")
                    print(f"  Status: {status}")
                    print(f"  Account: {account}")
                    if info.get('arn'):
                        print(f"  ARN: {info['arn']}")
                    if info.get('error'):
                        print(f"  Error: {info['error']}")
                    print()
            
            case 'list-environments':
                environments = manager.list_environments()
                print("🌍 Available Environments:")
                for name, config in environments.items():
                    print(f"  • {name}: {config['description']} ({config['region']})")
            
            case 'list-buckets':
                result = manager.list_s3_buckets()
                if result['success']:
                    print("🪣 S3 Buckets:")
                    for bucket in result['buckets']:
                        print(f"  • {bucket['name']} (created: {bucket['creation_date']})")
                else:
                    print(f"❌ {result['message']}")
            
            case 'list-s3':
                if len(sys.argv) < 3:
                    print("❌ Bucket name required")
                    return
                bucket_name = sys.argv[2]
                prefix = sys.argv[3] if len(sys.argv) > 3 else ''
                result = manager.list_s3_objects(bucket_name, prefix)
                if result['success']:
                    print(f"📁 S3 Objects in {bucket_name}:")
                    for folder in result['folders']:
                        print(f"  📁 {folder['name']}")
                    for obj in result['objects']:
                        print(f"  📄 {obj['name']} ({obj['size']} bytes)")
                else:
                    print(f"❌ {result['message']}")
            
            case 'assume-role':
                if len(sys.argv) < 3:
                    print("❌ Role ARN required")
                    return
                role_arn = sys.argv[2]
                session_name = sys.argv[3] if len(sys.argv) > 3 else 'temp-session'
                profile_name = sys.argv[4] if len(sys.argv) > 4 else 'assumed-role'
                source_profile = sys.argv[5] if len(sys.argv) > 5 else None
                result = manager.assume_role(role_arn, session_name, profile_name=profile_name, source_profile=source_profile)
                if result['success']:
                    print("✅ Role assumed successfully")
                    print(f"Profile: {result.get('profile_name', 'N/A')}")
                    print(f"Access Key: {result['credentials']['AccessKeyId'][:20]}...")
                    print(f"Expires: {result['credentials']['Expiration']}")
                    print(f"\n💡 Usage: aws s3 ls --profile {result.get('profile_name', 'assumed-role')}")
                else:
                    print(f"❌ {result['message']}")
            
            case 'setup-assume-roles':
                print("🔧 Setting up assume role profiles from config...")
                results = manager.create_assume_role_profiles_from_config()
                if results:
                    print("\n📋 Results:")
                    for profile_name, success in results.items():
                        status = "✅" if success else "❌"
                        print(f"  {status} {profile_name}")
                    print(f"\n✅ Created {sum(results.values())}/{len(results)} profiles successfully")
                    print("\n💡 Usage examples:")
                    for profile_name in results.keys():
                        if results[profile_name]:
                            print(f"  aws s3 ls --profile {profile_name}")
                else:
                    print("❌ No assume_role_configs found in config.json")
            
            case 'use-role':
                if len(sys.argv) < 3:
                    print("❌ Configuration name required")
                    print("\nAvailable role configurations:")
                    assume_configs = manager.config_manager.get_assume_role_configs()
                    for name, config in assume_configs.items():
                        print(f"  • {name}: {config.get('description', 'No description')}")
                    print("\n💡 Usage:")
                    print("  python main.py use-role <name> [method]")
                    print("  Methods: script (for CLI) or boto3 (for Python)")
                    return
                
                config_name = sys.argv[2]
                method = sys.argv[3] if len(sys.argv) > 3 else 'script'
                
                print(f"🔧 Assuming role: {config_name} (method: {method})")
                result = manager.assume_role_via_script(config_name, method)
                
                if result['success']:
                    if method == 'script':
                        print(result.get('instructions', ''))
                    else:  # boto3
                        print(f"✅ Role assumed successfully!")
                        print(f"Profile: {result.get('profile_name', 'N/A')}")
                        print(f"Expires: {result.get('credentials', {}).get('Expiration', 'N/A')}")
                        print(f"\n💡 Usage with AWS CLI:")
                        print(f"  aws s3 ls --profile {result.get('profile_name', config_name)}")
                else:
                    print(f"❌ {result['message']}")

            case 'env-vars':
                import os
                print("🔧 Current AWS Environment Variables:")
                print("=" * 60)

                aws_vars = {
                    'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID'),
                    'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY'),
                    'AWS_SESSION_TOKEN': os.environ.get('AWS_SESSION_TOKEN'),
                    'AWS_PROFILE': os.environ.get('AWS_PROFILE'),
                    'AWS_DEFAULT_REGION': os.environ.get('AWS_DEFAULT_REGION'),
                    'AWS_REGION': os.environ.get('AWS_REGION')
                }

                for var_name, value in aws_vars.items():
                    if value:
                        if 'SECRET' in var_name or 'KEY' in var_name:
                            display_value = value[:10] + '...' if len(value) > 10 else value
                        elif 'TOKEN' in var_name:
                            display_value = 'Set' if value else 'Not set'
                        else:
                            display_value = value
                        print(f"✅ {var_name}: {display_value}")
                    else:
                        print(f"❌ {var_name}: Not set")

                print(f"\n📍 Python Path: {sys.executable}")
                print(f"📍 Working Directory: {os.getcwd()}")

            case 'clean-creds':
                print("🧹 Cleaning expired credentials from AWS credentials file...")
                result = manager.clean_expired_credentials()
                if result['success']:
                    cleaned_count = result.get('cleaned_count', 0)
                    if cleaned_count > 0:
                        print(f"✅ Cleaned {cleaned_count} expired credential profile(s)")
                    else:
                        print("✅ No expired credentials found")
                else:
                    print(f"❌ {result['message']}")

            case _:
                print(f"❌ Unknown command: {command}")
                print_usage()
    
    except Exception as e:
        logger.error(f"CLI error: {e}")
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()
