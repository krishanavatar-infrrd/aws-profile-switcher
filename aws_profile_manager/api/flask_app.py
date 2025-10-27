from flask import Flask, render_template, request, jsonify, flash, session
from aws_profile_manager.core.manager import AWSProfileManager
from aws_profile_manager.utils.logging import setup_logging
from aws_profile_manager.api.session_manager import SessionManager
import logging
import os
import configparser
from pathlib import Path

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize AWS Profile Manager
aws_manager = AWSProfileManager()

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

    # Get config from manager
    config = aws_manager.config_manager.config
    config_path = Path.home() / '.aws' / 'config'

    if config_path.exists():
        config_parser = configparser.ConfigParser()
        config_parser.read(config_path)

        if 'profile default' in config_parser.sections():
            profile_config = config_parser['profile default']
            current_role = profile_config.get('role_arn', '')
            current_region = profile_config.get('region', '')

            # Find matching environment
            for env_name, env_config in config.get('environments', {}).items():
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

def create_app():
    app = Flask(__name__, template_folder="../../templates")
    app.secret_key = 'your-secret-key-here'

    # Initialize session manager for credential management
    session_manager = SessionManager(app)
    
    @app.route('/')
    def index():
        try:
            status = aws_manager.get_status()
            current_profile = status.get('current_profile', 'None')
            current_env = get_current_environment_info()
            credentials_status = aws_manager.get_credentials_status()
            environments = aws_manager.list_environments()
            base_credentials_path = aws_manager.config_manager.get_base_credentials_path()
            
            return render_template('index.html', 
                                 environments=environments, 
                                 current_profile=current_profile,
                                 current_env=current_env,
                                 credentials_status=credentials_status,
                                 base_credentials_path=base_credentials_path,
                                 status=status)
        except Exception as e:
            logger.error(f'Error in index: {e}')
            return render_template('index.html', 
                                 environments={}, 
                                 current_profile='None',
                                 current_env={},
                                 credentials_status={},
                                 base_credentials_path='',
                                 status={})
    
    @app.route('/profiles')
    def profiles():
        try:
            profiles = aws_manager.list_profiles()
            status = aws_manager.get_status()
            credentials_profiles = aws_manager.config_manager.get_credentials_profiles()
            return render_template('profiles.html', 
                                 profiles=profiles, 
                                 current_profile=status['current_profile'],
                                 credentials_profiles=credentials_profiles)
        except Exception as e:
            logger.error(f'Error in profiles: {e}')
            return render_template('profiles.html', 
                                 profiles={}, 
                                 current_profile=None,
                                 credentials_profiles={})
    
    @app.route('/environments')
    def environments():
        try:
            environments = aws_manager.list_environments()
            current_env = get_current_environment_info()
            return render_template('environments.html', 
                                 environments=environments, 
                                 current_env=current_env)
        except Exception as e:
            logger.error(f'Error in environments: {e}')
            return render_template('environments.html', environments={}, current_env={})
    
    @app.route('/credentials')
    def credentials():
        try:
            status = aws_manager.get_status()
            credentials_status = aws_manager.get_credentials_status()
            base_credentials_path = aws_manager.config_manager.get_base_credentials_path()
            return render_template('credentials.html', 
                                 status=status, 
                                 credentials_status=credentials_status,
                                 base_credentials_path=base_credentials_path)
        except Exception as e:
            logger.error(f'Error in credentials: {e}')
            return render_template('credentials.html', 
                                 status={}, 
                                 credentials_status={
                                     'base_file_exists': False,
                                     'default_profile_valid': False,
                                     'infrrd_master_valid': False,
                                     'in_sync': False,
                                     'base_access_key': 'N/A',
                                     'default_access_key': 'N/A',
                                     'infrrd_access_key': 'N/A'
                                 },
                                 base_credentials_path='')
    
    @app.route('/s3')
    def s3():
        try:
            return render_template('s3.html')
        except Exception as e:
            logger.error(f'Error in s3: {e}')
            return render_template('s3.html')
    
    @app.route('/assume-role-page')
    def assume_role_page():
        try:
            assume_role_configs = aws_manager.config_manager.get_assume_role_configs()
            return render_template('assume_role.html', assume_role_configs=assume_role_configs)
        except Exception as e:
            logger.error(f'Error in assume role page: {e}')
            return render_template('assume_role.html', assume_role_configs={})
    
    
    # API Endpoints
    @app.route('/api/switch_profile', methods=['POST'])
    def api_switch_profile():
        """API endpoint to switch profile"""
        try:
            data = request.get_json()
            profile_name = data.get('profile_name')
            
            if not profile_name:
                return jsonify({'success': False, 'message': 'Profile name is required'})
            
            result = aws_manager.switch_profile(profile_name)
            
            if result:
                return jsonify({'success': True, 'message': f'Switched to {profile_name} profile'})
            else:
                return jsonify({'success': False, 'message': f'Failed to switch to {profile_name} profile'})
                
        except Exception as e:
            logger.error(f"Error switching profile: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/switch_environment', methods=['POST'])
    def api_switch_environment():
        """API endpoint to switch environment"""
        try:
            data = request.get_json()
            env_name = data.get('env_name')
            
            if not env_name:
                return jsonify({'success': False, 'message': 'Environment name is required'})
            
            # Clear any existing assumed role credentials first
            if 'assumed_credentials' in session:
                logger.info("Clearing existing assumed role before environment switch")
                session_manager.clear_assumed_credentials()
            
            result = aws_manager.switch_environment(env_name)
            
            if result:
                # Force boto3 to reload credentials by clearing the credential cache
                import boto3
                boto3.setup_default_session()
                logger.info("Cleared boto3 session cache to reload credentials")
                
                return jsonify({
                    'success': True, 
                    'message': f'Switched to {env_name.upper()} environment. Credentials reloaded.',
                    'requires_reload': True
                })
            else:
                return jsonify({'success': False, 'message': f'Failed to switch to {env_name} environment'})
                
        except Exception as e:
            logger.error(f"Error switching environment: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/sync_credentials', methods=['POST'])
    def api_sync_credentials():
        """API endpoint to sync credentials"""
        try:
            result = aws_manager.sync_credentials()
            return jsonify({'success': result, 'message': 'Credentials synced successfully' if result else 'Failed to sync credentials'})
        except Exception as e:
            logger.error(f"Error syncing credentials: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/update_base_credentials_path', methods=['POST'])
    def api_update_base_credentials_path():
        """API endpoint to update base credentials file path"""
        try:
            data = request.get_json()
            new_path = data.get('base_credentials_path')

            if not new_path:
                return jsonify({'success': False, 'message': 'Base credentials path is required'})

            # Update config
            config = aws_manager.config_manager.config
            config['base_credentials_path'] = new_path
            aws_manager.config_manager.save_config()

            return jsonify({'success': True, 'message': f'Base credentials path updated to: {new_path}'})

        except Exception as e:
            logger.error(f"Error updating base credentials path: {e}")
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})

    @app.route('/api/force_refresh', methods=['POST'])
    def api_force_refresh():
        """API endpoint to force refresh credentials"""
        try:
            # Force sync credentials from base file
            result = aws_manager.sync_credentials()
            return jsonify({'success': result, 'message': 'Credentials refreshed successfully' if result else 'Failed to refresh credentials'})
        except Exception as e:
            logger.error(f"Error force refreshing credentials: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/clean_config', methods=['POST'])
    def api_clean_config():
        """API endpoint to clean config file"""
        try:
            # This would clean up the AWS config file to have only one active environment
            config_path = Path.home() / '.aws' / 'config'
            
            if config_path.exists():
                config_parser = configparser.ConfigParser()
                config_parser.read(config_path)
                
                # Remove all profile sections except default
                sections_to_remove = [section for section in config_parser.sections() if section.startswith('profile ') and section != 'profile default']
                for section in sections_to_remove:
                    config_parser.remove_section(section)
                
                # Write back the cleaned config
                with open(config_path, 'w') as f:
                    config_parser.write(f)
            
            return jsonify({'success': True, 'message': 'Config file cleaned successfully'})
        except Exception as e:
            logger.error(f"Error cleaning config: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/status', methods=['GET'])
    def api_status():
        """API endpoint to get status"""
        try:
            status = aws_manager.get_status()

            # Add session information using session manager
            session_info = session_manager.get_session_info()

            # Determine the correct current profile
            # If we have assumed credentials, use the original profile that was stored
            # Otherwise, use the current AWS_PROFILE environment variable
            current_profile = status.get('current_profile', 'default')
            if session_info.get('session_credentials_active'):
                # When role is assumed, get the original profile from session manager
                if hasattr(session_manager.app, '_original_aws_profile'):
                    current_profile = session_manager.app._original_aws_profile
                else:
                    # Fallback to default if no original profile stored
                    current_profile = 'default'
            else:
                # No assumed credentials, use current AWS_PROFILE or default
                current_profile = os.environ.get('AWS_PROFILE', 'default')

            # Override the profile in status
            status['current_profile'] = current_profile

            # Determine the correct current environment
            # If we have assumed credentials, try to get environment from session info
            current_environment = status.get('current_environment')
            if session_info.get('session_credentials_active') and session_info.get('assumed_role'):
                # When role is assumed, show the role name as environment
                current_environment = session_info['assumed_role']
            elif current_environment is None:
                current_environment = 'Unknown'

            # Override the environment in status
            status['current_environment'] = current_environment

            # Add current environment variables for debugging
            env_info = {
                'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID', 'Not set')[:10] + '...' if os.environ.get('AWS_ACCESS_KEY_ID') else 'Not set',
                'AWS_PROFILE': os.environ.get('AWS_PROFILE', 'Not set'),
                'AWS_SESSION_TOKEN': 'Set' if os.environ.get('AWS_SESSION_TOKEN') else 'Not set'
            }

            status.update({
                'session': session_info,
                'environment': env_info,
                'success': True
            })
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return jsonify({'error': str(e)})
    


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

            result = aws_manager.save_credentials(profile_name, access_key, secret_key, session_token)
            
            if result:
                return jsonify({'success': True, 'message': f'Credentials for {profile_name} updated successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to update credentials for {profile_name}'})
                
        except Exception as e:
            logger.error(f"Error updating credentials: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/create_role_profile', methods=['POST'])
    def api_create_role_profile():
        """API endpoint to create role-based profile"""
        try:
            data = request.get_json()
            profile_name = data.get('profile_name')
            role_arn = data.get('role_arn')
            source_profile = data.get('source_profile', 'infrrd-master')
            region = data.get('region', 'us-east-1')

            if not profile_name or not role_arn:
                return jsonify({'success': False, 'message': 'Profile name and role ARN are required'})

            result = aws_manager.save_role_profile(profile_name, role_arn, source_profile)
            
            if result:
                return jsonify({'success': True, 'message': f'Role profile {profile_name} created successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to create role profile {profile_name}'})
                
        except Exception as e:
            logger.error(f"Error creating role profile: {e}")
            return jsonify({'success': False, 'message': str(e)})

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
            config = aws_manager.config_manager.config
            if 'credentials_profiles' not in config:
                config['credentials_profiles'] = {}
            
            config['credentials_profiles'][profile_name] = {
                'type': 'credentials',
                'description': description
            }
            
            result = aws_manager.config_manager.save_config()
            
            if result:
                return jsonify({'success': True, 'message': f'Credential profile {profile_name} added to configuration'})
            else:
                return jsonify({'success': False, 'message': f'Failed to save configuration'})
                
        except Exception as e:
            logger.error(f"Error adding credential profile: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/remove_config_profile', methods=['POST'])
    def api_remove_config_profile():
        """API endpoint to remove a credential profile from config"""
        try:
            data = request.get_json()
            profile_name = data.get('profile_name')

            if not profile_name:
                return jsonify({'success': False, 'message': 'Profile name is required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'credentials_profiles' in config and profile_name in config['credentials_profiles']:
                del config['credentials_profiles'][profile_name]
                result = aws_manager.config_manager.save_config()
                
                if result:
                    return jsonify({'success': True, 'message': f'Credential profile {profile_name} removed from configuration'})
                else:
                    return jsonify({'success': False, 'message': f'Failed to save configuration'})
            else:
                return jsonify({'success': False, 'message': f'Profile {profile_name} not found in configuration'})
                
        except Exception as e:
            logger.error(f"Error removing credential profile: {e}")
            return jsonify({'success': False, 'message': str(e)})


    @app.route('/api/add_environment', methods=['POST'])
    def api_add_environment():
        """API endpoint to add a new environment"""
        try:
            data = request.get_json()
            env_name = data.get('env_name')
            region = data.get('region', 'us-east-1')
            role_arn = data.get('role_arn')
            description = data.get('description', '')

            if not env_name or not role_arn:
                return jsonify({'success': False, 'message': 'Environment name and role ARN are required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'environments' not in config:
                config['environments'] = {}
            
            config['environments'][env_name] = {
                'region': region,
                'role_arn': role_arn,
                'description': description
            }
            
            result = aws_manager.config_manager.save_config()
            
            if result:
                return jsonify({'success': True, 'message': f'Environment {env_name} added successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to save configuration'})
                
        except Exception as e:
            logger.error(f"Error adding environment: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/update_environment', methods=['POST'])
    def api_update_environment():
        """API endpoint to update an existing environment"""
        try:
            data = request.get_json()
            env_name = data.get('env_name')
            region = data.get('region', 'us-east-1')
            role_arn = data.get('role_arn')
            description = data.get('description', '')

            if not env_name or not role_arn:
                return jsonify({'success': False, 'message': 'Environment name and role ARN are required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'environments' in config and env_name in config['environments']:
                config['environments'][env_name] = {
                    'region': region,
                    'role_arn': role_arn,
                    'description': description
                }
                
                result = aws_manager.config_manager.save_config()
                
                if result:
                    return jsonify({'success': True, 'message': f'Environment {env_name} updated successfully'})
                else:
                    return jsonify({'success': False, 'message': f'Failed to save configuration'})
            else:
                return jsonify({'success': False, 'message': f'Environment {env_name} not found'})
                
        except Exception as e:
            logger.error(f"Error updating environment: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/remove_environment', methods=['POST'])
    def api_remove_environment():
        """API endpoint to remove an environment"""
        try:
            data = request.get_json()
            env_name = data.get('env_name')

            if not env_name:
                return jsonify({'success': False, 'message': 'Environment name is required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'environments' in config and env_name in config['environments']:
                del config['environments'][env_name]
                result = aws_manager.config_manager.save_config()
                
                if result:
                    return jsonify({'success': True, 'message': f'Environment {env_name} removed successfully'})
                else:
                    return jsonify({'success': False, 'message': f'Failed to save configuration'})
            else:
                return jsonify({'success': False, 'message': f'Environment {env_name} not found'})
                
        except Exception as e:
            logger.error(f"Error removing environment: {e}")
            return jsonify({'success': False, 'message': str(e)})


    @app.route('/api/assume_role', methods=['POST'])
    def api_assume_role():
        """API endpoint to assume an AWS role"""
        try:
            data = request.get_json()
            role_arn = data.get('role_arn')
            session_name = data.get('session_name', 'temp-session')
            external_id = data.get('external_id')
            duration = data.get('duration', 3600)
            profile_name = data.get('config_name', 'assumed-role')
            source_profile = data.get('source_profile')  # Allow specifying source profile

            if not role_arn:
                return jsonify({'success': False, 'message': 'Role ARN is required'})

            # Use the role manager to assume the role (don't save to file for web interface)
            result = aws_manager.assume_role(role_arn, session_name, external_id, duration, profile_name=profile_name, save_to_profile=False, source_profile=source_profile)

            if result.get('success'):
                # Store credentials in session for cross-tab usage using session manager
                session_manager.set_assumed_credentials(result.get('credentials'), profile_name)

                return jsonify({
                    'success': True,
                    'message': 'Role assumed successfully',
                    'profile_name': result.get('profile_name'),
                    'credentials': result.get('credentials'),
                    'session_active': True
                })
            else:
                return jsonify({
                    'success': False,
                    'message': result.get('message', 'Failed to assume role')
                })

        except Exception as e:
            logger.error(f"Error assuming role: {e}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/assume_role_script', methods=['POST'])
    def api_assume_role_script():
        """API endpoint to generate assume role script"""
        try:
            data = request.get_json()
            config_name = data.get('config_name')
            
            if not config_name:
                return jsonify({'success': False, 'message': 'Configuration name is required'})

            # Get the role config
            assume_role_configs = aws_manager.config_manager.get_assume_role_configs()
            if config_name not in assume_role_configs:
                return jsonify({'success': False, 'message': f'Role configuration "{config_name}" not found'})
            
            config = assume_role_configs[config_name]
            
            # Generate script at fixed location
            from pathlib import Path
            script_path = Path.home() / 'assume-role.sh'
            
            script_content = f"""#!/bin/bash
# Auto-generated AWS Assume Role Script
# Current Role: {config_name}
# Description: {config.get('description', 'No description')}
# Generated: {Path(__file__).stat().st_mtime}

# Clear previously assumed role credentials
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo "🔄 Clearing previous AWS credentials..."
echo "🔐 Assuming role: {config_name}..."

response=$(aws sts assume-role \\
  --role-arn {config.get('role_arn')} \\
  --role-session-name {config.get('session_name')}"""
            
            if config.get('external_id'):
                script_content += f""" \\
  --external-id {config.get('external_id')}"""
            
            script_content += """ 2>&1)

# Check if assume-role was successful
if [ $? -ne 0 ]; then
  echo "❌ Failed to assume role"
  echo "$response"
  return 1
fi

# Parse and export credentials using jq
export AWS_ACCESS_KEY_ID=$(echo "$response" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$response" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$response" | jq -r '.Credentials.SessionToken')

echo "✅ Successfully assumed role: """ + config_name + """\"
echo "📌 You can now use: aws s3 ls"
echo "⏰ Credentials will expire in 1 hour"
"""
            
            # Write script
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            logger.info(f"Generated assume role script for {config_name} at {script_path}")
            
            return jsonify({
                'success': True, 
                'message': f'Script generated for {config_name}',
                'script_path': str(script_path),
                'instructions': f'Run: source {script_path}'
            })
                
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/remove_assume_role', methods=['POST'])
    def api_remove_assume_role():
        """API endpoint to remove assumed role credentials"""
        try:
            data = request.get_json()
            profile_name = data.get('profile_name', 'assumed-role')

            # Check if we have session-based credentials (web interface)
            session_info = session_manager.get_session_info()
            if session_info.get('session_credentials_active'):
                # For web interface, just clear session credentials
                logger.info(f"Removing assumed role: {session_info.get('assumed_role')}")
                session_manager.clear_assumed_credentials()
                logger.info("Assumed role credentials removed from session")
                return jsonify({
                    'success': True,
                    'message': 'Assumed role credentials removed successfully',
                    'profile_name': profile_name
                })

            # For CLI/file-based credentials, remove from credentials file
            result = aws_manager.remove_assume_role(profile_name)

            if result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'Assumed role credentials removed successfully',
                    'profile_name': profile_name
                })
            else:
                return jsonify({
                    'success': False,
                    'message': result.get('message', 'Failed to remove assumed role')
                })

        except Exception as e:
            logger.error(f"Error removing assume role: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/add_assume_role_config', methods=['POST'])
    def api_add_assume_role_config():
        """API endpoint to add a new assume role configuration"""
        try:
            data = request.get_json()
            config_name = data.get('config_name')
            description = data.get('description')
            role_arn = data.get('role_arn')
            session_name = data.get('session_name')
            external_id = data.get('external_id')
            duration = data.get('duration', 3600)

            if not all([config_name, description, role_arn, session_name]):
                return jsonify({'success': False, 'message': 'Configuration name, description, role ARN, and session name are required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'assume_role_configs' not in config:
                config['assume_role_configs'] = {}
            
            config['assume_role_configs'][config_name] = {
                'role_arn': role_arn,
                'session_name': session_name,
                'external_id': external_id,
                'duration': duration,
                'description': description
            }
            
            result = aws_manager.config_manager.save_config()
            
            if result:
                return jsonify({'success': True, 'message': f'Role configuration {config_name} added successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to save configuration'})
                
        except Exception as e:
            logger.error(f"Error adding assume role config: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/update_assume_role_config', methods=['POST'])
    def api_update_assume_role_config():
        """API endpoint to update an existing assume role configuration"""
        try:
            data = request.get_json()
            config_name = data.get('config_name')
            description = data.get('description')
            role_arn = data.get('role_arn')
            session_name = data.get('session_name')
            external_id = data.get('external_id')
            duration = data.get('duration', 3600)

            if not all([config_name, description, role_arn, session_name]):
                return jsonify({'success': False, 'message': 'Configuration name, description, role ARN, and session name are required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'assume_role_configs' not in config:
                return jsonify({'success': False, 'message': 'No assume role configurations found'})
            
            if config_name not in config['assume_role_configs']:
                return jsonify({'success': False, 'message': f'Configuration {config_name} not found'})
            
            config['assume_role_configs'][config_name] = {
                'role_arn': role_arn,
                'session_name': session_name,
                'external_id': external_id,
                'duration': duration,
                'description': description
            }
            
            result = aws_manager.config_manager.save_config()
            
            if result:
                return jsonify({'success': True, 'message': f'Role configuration {config_name} updated successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to save configuration'})
                
        except Exception as e:
            logger.error(f"Error updating assume role config: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/delete_assume_role_config', methods=['POST'])
    def api_delete_assume_role_config():
        """API endpoint to delete an assume role configuration"""
        try:
            data = request.get_json()
            config_name = data.get('config_name')

            if not config_name:
                return jsonify({'success': False, 'message': 'Configuration name is required'})

            # Update config
            config = aws_manager.config_manager.config
            if 'assume_role_configs' not in config:
                return jsonify({'success': False, 'message': 'No assume role configurations found'})
            
            if config_name not in config['assume_role_configs']:
                return jsonify({'success': False, 'message': f'Configuration {config_name} not found'})
            
            del config['assume_role_configs'][config_name]
            
            result = aws_manager.config_manager.save_config()
            
            if result:
                return jsonify({'success': True, 'message': f'Role configuration {config_name} deleted successfully'})
            else:
                return jsonify({'success': False, 'message': f'Failed to save configuration'})
                
        except Exception as e:
            logger.error(f"Error deleting assume role config: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/download_credentials')
    def api_download_credentials():
        """API endpoint to redirect to JumpCloud for credential download"""
        from flask import redirect
        return redirect('https://console.jumpcloud.com/login#/')

    @app.route('/api/list_s3_buckets', methods=['GET'])
    def api_list_s3_buckets():
        """API endpoint to list S3 buckets"""
        try:
            result = aws_manager.list_s3_buckets()
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error listing S3 buckets: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/list_s3_objects', methods=['GET'])
    def api_list_s3_objects():
        """API endpoint to list S3 objects"""
        try:
            bucket_name = request.args.get('bucket')
            prefix = request.args.get('prefix', '')
            max_keys = int(request.args.get('max_keys', 20))
            continuation_token = request.args.get('continuation_token')

            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            result = aws_manager.list_s3_objects(bucket_name, prefix, max_keys, continuation_token)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error listing S3 objects: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/download_s3_object', methods=['POST'])
    def api_download_s3_object():
        """API endpoint to download S3 object"""
        try:
            data = request.get_json()
            bucket_name = data.get('bucket')
            object_key = data.get('object_key')
            local_path = data.get('local_path')

            if not bucket_name or not object_key:
                return jsonify({'success': False, 'message': 'Bucket name and object key are required'})

            result = aws_manager.download_s3_file(bucket_name, object_key, local_path)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error downloading S3 object: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/search_s3_object', methods=['GET'])
    def api_search_s3_object():
        """API endpoint to search for S3 object by complete path"""
        try:
            bucket_name = request.args.get('bucket')
            object_key = request.args.get('key')

            if not bucket_name or not object_key:
                return jsonify({'success': False, 'message': 'Bucket name and object key are required'})

            result = aws_manager.search_s3_object_by_path(bucket_name, object_key)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error searching S3 object: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/get_s3_download_url', methods=['GET'])
    def api_get_s3_download_url():
        """API endpoint to get presigned download URL for S3 object"""
        try:
            bucket_name = request.args.get('bucket')
            object_key = request.args.get('key')
            expiration = int(request.args.get('expiration', 3600))

            if not bucket_name or not object_key:
                return jsonify({'success': False, 'message': 'Bucket name and object key are required'})

            result = aws_manager.get_s3_presigned_download_url(bucket_name, object_key, expiration)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error getting S3 download URL: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/get_s3_credential_info', methods=['GET'])
    def api_get_s3_credential_info():
        """API endpoint to get current S3 credential information"""
        try:
            result = aws_manager.get_s3_credential_info()
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error getting S3 credential info: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/list_available_profiles', methods=['GET'])
    def api_list_available_profiles():
        """API endpoint to list available AWS profiles and their account information"""
        try:
            result = aws_manager.list_available_profiles()
            return jsonify({'success': True, 'profiles': result})
        except Exception as e:
            logger.error(f"Error listing available profiles: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/get_predefined_buckets', methods=['GET'])
    def api_get_predefined_buckets():
        """API endpoint to get predefined buckets from config"""
        try:
            predefined_buckets = aws_manager.config_manager.get_predefined_buckets()
            return jsonify({'success': True, 'buckets': predefined_buckets})
        except Exception as e:
            logger.error(f"Error getting predefined buckets: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/add_custom_bucket', methods=['POST'])
    def api_add_custom_bucket():
        """API endpoint to add a custom bucket"""
        try:
            data = request.get_json()
            bucket_name = data.get('bucket_name')

            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            # Add to config
            config = aws_manager.config_manager.config
            if 'custom_buckets' not in config:
                config['custom_buckets'] = []

            if bucket_name not in config['custom_buckets']:
                config['custom_buckets'].append(bucket_name)
                aws_manager.config_manager.save_config()
                return jsonify({'success': True, 'message': f'Bucket {bucket_name} added successfully'})
            else:
                return jsonify({'success': False, 'message': f'Bucket {bucket_name} already exists'})

        except Exception as e:
            logger.error(f"Error adding custom bucket: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/delete_custom_bucket', methods=['POST'])
    def api_delete_custom_bucket():
        """API endpoint to delete a custom bucket"""
        try:
            data = request.get_json()
            bucket_name = data.get('bucket_name')

            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            # Remove from config
            config = aws_manager.config_manager.config
            if 'custom_buckets' in config and bucket_name in config['custom_buckets']:
                config['custom_buckets'].remove(bucket_name)
                aws_manager.config_manager.save_config()
                return jsonify({'success': True, 'message': f'Bucket {bucket_name} removed successfully'})
            else:
                return jsonify({'success': False, 'message': f'Bucket {bucket_name} not found'})

        except Exception as e:
            logger.error(f"Error deleting custom bucket: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/list_custom_buckets', methods=['GET'])
    def api_list_custom_buckets():
        """API endpoint to list custom buckets"""
        try:
            config = aws_manager.config_manager.config
            custom_buckets = config.get('custom_buckets', [])
            return jsonify({'success': True, 'buckets': custom_buckets})
        except Exception as e:
            logger.error(f"Error listing custom buckets: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/add_predefined_bucket', methods=['POST'])
    def api_add_predefined_bucket():
        """API endpoint to add a predefined bucket"""
        try:
            data = request.get_json()
            bucket_name = data.get('bucket_name')

            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            config = aws_manager.config_manager.config
            if 'predefined_buckets' not in config:
                config['predefined_buckets'] = []

            if bucket_name not in config['predefined_buckets']:
                config['predefined_buckets'].append(bucket_name)
                aws_manager.config_manager.save_config()
                return jsonify({'success': True, 'message': f'Bucket {bucket_name} added to predefined list'})
            else:
                return jsonify({'success': False, 'message': f'Bucket {bucket_name} already exists in predefined list'})

        except Exception as e:
            logger.error(f"Error adding predefined bucket: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/update_predefined_bucket', methods=['POST'])
    def api_update_predefined_bucket():
        """API endpoint to update a predefined bucket"""
        try:
            data = request.get_json()
            old_bucket_name = data.get('old_bucket_name')
            new_bucket_name = data.get('new_bucket_name')

            if not old_bucket_name or not new_bucket_name:
                return jsonify({'success': False, 'message': 'Both old and new bucket names are required'})

            config = aws_manager.config_manager.config
            if 'predefined_buckets' in config and old_bucket_name in config['predefined_buckets']:
                index = config['predefined_buckets'].index(old_bucket_name)
                config['predefined_buckets'][index] = new_bucket_name
                aws_manager.config_manager.save_config()
                return jsonify({'success': True, 'message': f'Bucket updated from {old_bucket_name} to {new_bucket_name}'})
            else:
                return jsonify({'success': False, 'message': f'Bucket {old_bucket_name} not found in predefined list'})

        except Exception as e:
            logger.error(f"Error updating predefined bucket: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/delete_predefined_bucket', methods=['POST'])
    def api_delete_predefined_bucket():
        """API endpoint to delete a predefined bucket"""
        try:
            data = request.get_json()
            bucket_name = data.get('bucket_name')

            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            config = aws_manager.config_manager.config
            if 'predefined_buckets' in config and bucket_name in config['predefined_buckets']:
                config['predefined_buckets'].remove(bucket_name)
                aws_manager.config_manager.save_config()
                return jsonify({'success': True, 'message': f'Bucket {bucket_name} removed from predefined list'})
            else:
                return jsonify({'success': False, 'message': f'Bucket {bucket_name} not found in predefined list'})

        except Exception as e:
            logger.error(f"Error deleting predefined bucket: {e}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/check_s3_bucket_access', methods=['GET'])
    def api_check_s3_bucket_access():
        """API endpoint to check if an S3 bucket is accessible"""
        try:
            bucket_name = request.args.get('bucket')
            if not bucket_name:
                return jsonify({'success': False, 'message': 'Bucket name is required'})

            result = aws_manager.check_s3_bucket_access(bucket_name)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error checking bucket access: {e}")
            return jsonify({'success': False, 'message': str(e)})
    return app

def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask application"""
    app = create_app()
    app.run(host=host, port=port, debug=debug)
