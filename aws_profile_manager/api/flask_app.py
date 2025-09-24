from flask import Flask, render_template, request, jsonify, flash
from aws_profile_manager.core.manager import AWSProfileManager
from aws_profile_manager.utils.logging import setup_logging
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
            buckets_result = aws_manager.list_s3_buckets()
            buckets = buckets_result.get('buckets', []) if buckets_result['success'] else []
            return render_template('s3.html', buckets=buckets)
        except Exception as e:
            logger.error(f'Error in s3: {e}')
            return render_template('s3.html', buckets=[])
    
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
            
            result = aws_manager.switch_environment(env_name)
            
            if result:
                return jsonify({'success': True, 'message': f'Switched to {env_name.upper()} environment'})
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

            if not role_arn:
                return jsonify({'success': False, 'message': 'Role ARN is required'})

            # Use the role manager to assume the role
            result = aws_manager.assume_role(role_arn, session_name, external_id, duration)
            
            if result.get('success'):
                return jsonify({
                    'success': True, 
                    'message': 'Role assumed successfully',
                    'credentials': result.get('credentials')
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': result.get('message', 'Failed to assume role')
                })
                
        except Exception as e:
            logger.error(f"Error assuming role: {e}")
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
    return app

def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask application"""
    app = create_app()
    app.run(host=host, port=port, debug=debug)
