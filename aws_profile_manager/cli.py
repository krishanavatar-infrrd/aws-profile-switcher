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
    print("  assume-role <arn>       - Assume an AWS role")
    print("  list-profiles           - List all profiles")
    print("  list-environments       - List all environments")
    print("  list-buckets            - List S3 buckets")
    print("  list-s3 <bucket>        - List S3 objects in bucket")
    print("  download <bucket> <key> - Download S3 object")
    print("  upload <file> <bucket>  - Upload file to S3")
    print("  remove-profile <name>   - Remove a profile")
    print("  remove-env <name>       - Remove an environment")


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
                profiles = manager.list_profiles()
                print("📋 Available Profiles:")
                for name, config in profiles.items():
                    print(f"  • {name}")
            
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
                result = manager.assume_role(role_arn, session_name)
                if result['success']:
                    print("✅ Role assumed successfully")
                    print(f"Access Key: {result['credentials']['AccessKeyId']}")
                    print(f"Expires: {result['credentials']['Expiration']}")
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
