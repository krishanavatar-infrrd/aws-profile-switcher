#!/usr/bin/env python3
"""
AWS Profile Manager Flask Application
Web interface for managing AWS profiles and credentials
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import sys
import json
import configparser
from pathlib import Path
from datetime import datetime
import traceback

# Import the original AWSProfileManager class
from aws_profile_switcher import AWSProfileManager

app = Flask(__name__)
app.secret_key = 'aws-profile-manager-secret-key-2024'

# Configuration file path
CONFIG_FILE = Path('config.json')


def load_config():
    """Load configuration from JSON file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return get_default_config()
    else:
        return get_default_config()


def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def get_default_config():
    """Get default configuration"""
    return {
        "base_credentials_path": "/home/krishnavatar/Downloads/credentials",
        "environments": {
            "dev": {
                "region": "us-west-2",
                "role_arn": "arn:aws:iam::465825429380:role/AWS-SSO-Dev-Engineer",
                "description": "Development Environment"
            },
            "stage": {
                "region": "us-west-2",
                "role_arn": "arn:aws:iam::517080596001:role/AWS-SSO-Dev-Engineer",
                "description": "Staging Environment"
            },
            "swbcuat": {
                "region": "us-east-1",
                "role_arn": "arn:aws:iam::381492214186:role/AWS-SSO-Dev-Engineer",
                "description": "SWBC UAT Environment"
            },
            "swbcprod": {
                "region": "us-east-1",
                "role_arn": "arn:aws:iam::379233983907:role/AWS-SSO-Dev-Engineer",
                "description": "SWBC Production Environment"
            },
            "snprod": {
                "region": "us-west-2",
                "role_arn": "arn:aws:iam::448930163422:role/AWS-SSO-Dev-Engineer",
                "description": "SN Production Environment"
            },
            "eu-prod": {
                "region": "eu-west-1",
                "role_arn": "arn:aws:iam::832828561738:role/AWS-SSO-Dev-Engineer",
                "description": "EU Production Environment"
            }
        },
        "credentials_profiles": {
            "default": {
                "type": "credentials",
                "description": "Default AWS profile"
            },
            "infrrd-master": {
                "type": "credentials",
                "description": "Master credentials profile for role assumption"
            }
        }
    }


def get_aws_manager():
    """Get AWS manager instance with current config"""
    config = load_config()
    manager = AWSProfileManager()
    manager.base_credentials_path = Path(config['base_credentials_path'])
    manager.environments = config['environments']
    return manager


# Initialize the AWS Profile Manager
aws_manager = get_aws_manager()


@app.route('/')
def index():
    """Main dashboard"""
    try:
        # Get current profile info
        current_profile = os.environ.get('AWS_PROFILE', 'default')

        # Get profiles list
        profiles_info = get_profiles_info()

        # Get current environment info
        current_env = get_current_environment_info()

        # Get credentials status
        credentials_status = get_credentials_status()

        # Load current config
        config = load_config()

        return render_template('index.html',
                               current_profile=current_profile,
                               profiles=profiles_info,
                               current_env=current_env,
                               credentials_status=credentials_status,
                               environments=config['environments'],
                               base_credentials_path=config['base_credentials_path'])
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('index.html',
                               current_profile='unknown',
                               profiles={},
                               current_env={},
                               credentials_status={},
                               environments={},
                               base_credentials_path='')


@app.route('/profiles')
def profiles():
    """Profiles management page"""
    try:
        profiles_info = get_profiles_info()
        config = load_config()
        return render_template('profiles.html',
                               profiles=profiles_info,
                               credentials_profiles=config['credentials_profiles'])
    except Exception as e:
        flash(f'Error loading profiles: {str(e)}', 'error')
        return render_template('profiles.html',
                               profiles={},
                               credentials_profiles={})


@app.route('/environments')
def environments():
    """Environments management page"""
    try:
        current_env = get_current_environment_info()
        config = load_config()
        return render_template('environments.html',
                               environments=config['environments'],
                               current_env=current_env)
    except Exception as e:
        flash(f'Error loading environments: {str(e)}', 'error')
        return render_template('environments.html',
                               environments={},
                               current_env={})


@app.route('/credentials')
def credentials():
    """Credentials management page"""
    try:
        credentials_status = get_credentials_status()
        config = load_config()
        return render_template('credentials.html',
                               credentials_status=credentials_status,
                               base_credentials_path=config['base_credentials_path'])
    except Exception as e:
        flash(f'Error loading credentials: {str(e)}', 'error')
        return render_template('credentials.html',
                               credentials_status={},
                               base_credentials_path='')


@app.route('/api/switch_profile', methods=['POST'])
def api_switch_profile():
    """API endpoint to switch profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')

        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name is required'})

        aws_manager = get_aws_manager()
        success = aws_manager.switch_profile(profile_name)

        if success:
            return jsonify({'success': True, 'message': f'Switched to profile: {profile_name}'})
        else:
            return jsonify({'success': False, 'message': f'Failed to switch to profile: {profile_name}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/switch_environment', methods=['POST'])
def api_switch_environment():
    """API endpoint to switch environment"""
    try:
        data = request.get_json()
        env_name = data.get('env_name')

        if not env_name:
            return jsonify({'success': False, 'message': 'Environment name is required'})

        aws_manager = get_aws_manager()
        success = aws_manager.switch_environment(env_name)

        if success:
            return jsonify({'success': True, 'message': f'Switched to {env_name.upper()} environment'})
        else:
            return jsonify({'success': False, 'message': f'Failed to switch to {env_name} environment'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/sync_credentials', methods=['POST'])
def api_sync_credentials():
    """API endpoint to sync credentials from base file"""
    try:
        aws_manager = get_aws_manager()
        success = aws_manager.sync_credentials_from_base()

        if success:
            return jsonify({'success': True, 'message': 'Credentials synced successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to sync credentials'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/force_refresh', methods=['POST'])
def api_force_refresh():
    """API endpoint to force refresh credentials"""
    try:
        aws_manager = get_aws_manager()
        aws_manager.force_refresh_credentials()
        return jsonify({'success': True, 'message': 'Credentials refreshed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/clean_config', methods=['POST'])
def api_clean_config():
    """API endpoint to clean config file"""
    try:
        aws_manager = get_aws_manager()
        success = aws_manager.clean_config_file()

        if success:
            return jsonify({'success': True, 'message': 'Config file cleaned successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to clean config file'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/force_clean_reset', methods=['POST'])
def api_force_clean_reset():
    """API endpoint to force clean and reset"""
    try:
        aws_manager = get_aws_manager()
        aws_manager.force_clean_and_reset()
        return jsonify({'success': True, 'message': 'Config cleaned and reset successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/update_credentials', methods=['POST'])
def api_update_credentials():
    """API endpoint to update credentials"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name', 'default')
        access_key = data.get('access_key')
        secret_key = data.get('secret_key')
        session_token = data.get('session_token', '')

        if not access_key or not secret_key:
            return jsonify({'success': False, 'message': 'Access Key ID and Secret Access Key are required'})

        aws_manager = get_aws_manager()
        aws_manager.save_credentials(profile_name, access_key, secret_key, session_token)
        return jsonify({'success': True, 'message': f'Credentials for {profile_name} updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/create_role_profile', methods=['POST'])
def api_create_role_profile():
    """API endpoint to create role-based profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        source_profile = data.get('source_profile')
        role_arn = data.get('role_arn')
        region = data.get('region', '')
        duration = data.get('duration', '3600')

        if not profile_name or not source_profile or not role_arn:
            return jsonify({'success': False, 'message': 'Profile name, source profile, and role ARN are required'})

        aws_manager = get_aws_manager()
        aws_manager.save_role_profile(profile_name, source_profile, role_arn, region, duration)
        return jsonify({'success': True, 'message': f'Role-based profile {profile_name} created successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/remove_profile', methods=['POST'])
def api_remove_profile():
    """API endpoint to remove profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        profile_type = data.get('profile_type', 'credentials')  # 'credentials' or 'role'

        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name is required'})

        aws_manager = get_aws_manager()
        if profile_type == 'role':
            success = aws_manager.remove_role_profile(profile_name)
        else:
            success = aws_manager.remove_profile(profile_name)

        if success:
            return jsonify({'success': True, 'message': f'Profile {profile_name} removed successfully'})
        else:
            return jsonify({'success': False, 'message': f'Failed to remove profile {profile_name}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/update_base_credentials_path', methods=['POST'])
def api_update_base_credentials_path():
    """API endpoint to update base credentials file path"""
    try:
        data = request.get_json()
        new_path = data.get('base_credentials_path')

        if not new_path:
            return jsonify({'success': False, 'message': 'Base credentials path is required'})

        # Update config
        config = load_config()
        config['base_credentials_path'] = new_path
        save_config(config)

        return jsonify({'success': True, 'message': f'Base credentials path updated to: {new_path}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/add_credential_profile', methods=['POST'])
def api_add_credential_profile():
    """API endpoint to add a new credential profile to config"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        description = data.get('description', '')

        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name is required'})

        # Update config
        config = load_config()
        config['credentials_profiles'][profile_name] = {
            'type': 'credentials',
            'description': description
        }
        save_config(config)

        return jsonify({'success': True, 'message': f'Credential profile {profile_name} added to configuration'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/add_environment', methods=['POST'])
def api_add_environment():
    """API endpoint to add a new environment"""
    try:
        data = request.get_json()
        env_name = data.get('env_name')
        region = data.get('region')
        role_arn = data.get('role_arn')
        description = data.get('description', '')

        if not env_name or not region or not role_arn:
            return jsonify({'success': False, 'message': 'Environment name, region, and role ARN are required'})

        # Update config
        config = load_config()
        config['environments'][env_name] = {
            'region': region,
            'role_arn': role_arn,
            'description': description
        }
        save_config(config)

        return jsonify({'success': True, 'message': f'Environment {env_name} added successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/remove_environment', methods=['POST'])
def api_remove_environment():
    """API endpoint to remove an environment"""
    try:
        data = request.get_json()
        env_name = data.get('env_name')

        if not env_name:
            return jsonify({'success': False, 'message': 'Environment name is required'})

        # Update config
        config = load_config()
        if env_name in config['environments']:
            del config['environments'][env_name]
            save_config(config)
            return jsonify({'success': True, 'message': f'Environment {env_name} removed successfully'})
        else:
            return jsonify({'success': False, 'message': f'Environment {env_name} not found'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/remove_credential_profile', methods=['POST'])
def api_remove_credential_profile():
    """API endpoint to remove a credential profile from config"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')

        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name is required'})

        # Update config
        config = load_config()
        if profile_name in config['credentials_profiles']:
            del config['credentials_profiles'][profile_name]
            save_config(config)
            return jsonify(
                {'success': True, 'message': f'Credential profile {profile_name} removed from configuration'})
        else:
            return jsonify({'success': False, 'message': f'Credential profile {profile_name} not found'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/status')
def api_status():
    """API endpoint to get current status"""
    try:
        current_profile = os.environ.get('AWS_PROFILE', 'default')
        profiles_info = get_profiles_info()
        current_env = get_current_environment_info()
        credentials_status = get_credentials_status()
        config = load_config()

        return jsonify({
            'success': True,
            'data': {
                'current_profile': current_profile,
                'profiles': profiles_info,
                'current_env': current_env,
                'credentials_status': credentials_status,
                'base_credentials_path': config['base_credentials_path'],
                'environments': config['environments'],
                'credentials_profiles': config['credentials_profiles']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/api/download_credentials')
def api_download_credentials():
    """API endpoint to redirect to JumpCloud for credential download"""
    return redirect('https://console.jumpcloud.com/login')


def get_profiles_info():
    """Get profiles information for the UI"""
    profiles_info = {}

    # Read credentials file
    if aws_manager.credentials_path.exists():
        config = configparser.ConfigParser()
        config.read(aws_manager.credentials_path)

        for profile in config.sections():
            status = "valid" if aws_manager.is_profile_valid(config[profile]) else "invalid"
            profiles_info[profile] = {
                'type': 'credentials',
                'status': status,
                'has_credentials': True,
                'access_key': config[profile].get('aws_access_key_id', '')[:10] + '...' if config[profile].get(
                    'aws_access_key_id') else 'N/A'
            }

    # Read config file for role-based profiles
    if aws_manager.config_path.exists():
        config = configparser.ConfigParser()
        config.read(aws_manager.config_path)

        for profile in config.sections():
            if profile.startswith('profile '):
                profile_name = profile.replace('profile ', '')

                if profile_name not in profiles_info:
                    profiles_info[profile_name] = {
                        'type': 'role',
                        'status': 'role',
                        'has_credentials': False,
                        'access_key': 'N/A'
                    }
                else:
                    # Profile exists in both files
                    profiles_info[profile_name]['type'] = 'both'
                    profiles_info[profile_name]['status'] = 'both'

    return profiles_info


def get_current_environment_info():
    """Get current environment information"""
    current_profile = os.environ.get('AWS_PROFILE', 'default')
    current_env = {
        'profile': current_profile,
        'environment': 'Unknown',
        'region': 'N/A',
        'role_arn': 'N/A',
        'description': 'N/A'
    }

    config = load_config()

    if aws_manager.config_path.exists():
        config_parser = configparser.ConfigParser()
        config_parser.read(aws_manager.config_path)

        if 'profile default' in config_parser.sections():
            profile_config = config_parser['profile default']
            current_role = profile_config.get('role_arn', '')
            current_region = profile_config.get('region', '')

            # Find matching environment
            for env_name, env_config in config['environments'].items():
                if (env_config['role_arn'] == current_role and
                        env_config['region'] == current_region):
                    current_env.update({
                        'environment': env_name.upper(),
                        'region': env_config['region'],
                        'role_arn': env_config['role_arn'],
                        'description': env_config['description']
                    })
                    break

    return current_env


def get_credentials_status():
    """Get credentials status information"""
    status = {
        'base_file_exists': False,
        'base_credentials_valid': False,
        'aws_credentials_exists': False,
        'default_profile_valid': False,
        'infrrd_master_valid': False,
        'in_sync': False,
        'base_access_key': 'N/A',
        'default_access_key': 'N/A',
        'infrrd_access_key': 'N/A'
    }

    aws_manager = get_aws_manager()

    # Check base file
    if aws_manager.base_credentials_path.exists():
        status['base_file_exists'] = True
        try:
            with open(aws_manager.base_credentials_path, 'r') as f:
                base_content = f.read()
            base_creds = aws_manager.parse_base_credentials(base_content)
            if base_creds:
                status['base_credentials_valid'] = True
                status['base_access_key'] = base_creds['aws_access_key_id'][:10] + '...'
        except:
            pass

    # Check AWS credentials file
    if aws_manager.credentials_path.exists():
        status['aws_credentials_exists'] = True
        config = configparser.ConfigParser()
        config.read(aws_manager.credentials_path)

        # Check default profile
        if 'default' in config.sections():
            if aws_manager.is_profile_valid(config['default']):
                status['default_profile_valid'] = True
                status['default_access_key'] = config['default']['aws_access_key_id'][:10] + '...'

        # Check infrrd-master profile
        if 'infrrd-master' in config.sections():
            if aws_manager.is_profile_valid(config['infrrd-master']):
                status['infrrd_master_valid'] = True
                status['infrrd_access_key'] = config['infrrd-master']['aws_access_key_id'][:10] + '...'

    # Check if in sync
    if (status['base_file_exists'] and status['aws_credentials_exists'] and
            status['base_credentials_valid'] and status['default_profile_valid'] and
            status['infrrd_master_valid']):

        if (status['base_access_key'] == status['default_access_key'] ==
                status['infrrd_access_key']):
            status['in_sync'] = True

    return status


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)