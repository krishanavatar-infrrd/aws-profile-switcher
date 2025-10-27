"""
Session-based credential management for AWS Profile Manager
"""

import os
from datetime import datetime, timezone, timedelta
from flask import session
from typing import Optional


class SessionManager:
    """Manages session-based AWS credentials across browser tabs"""

    def __init__(self, app):
        self.app = app
        self._original_aws_profile = None
        self._original_credentials = None

        # Set up request hooks
        self._setup_request_hooks()

    def _setup_request_hooks(self):
        """Set up Flask request hooks for credential management"""

        @self.app.before_request
        def load_session_credentials():
            """Load assumed credentials from session if available and not expired"""
            self.app.logger.debug(f"Session check - assumed_credentials in session: {'assumed_credentials' in session}")

            if 'assumed_credentials' in session:
                creds = session['assumed_credentials']
                expiration = datetime.fromisoformat(creds['Expiration'].replace('Z', '+00:00'))

                # Check if credentials are expired (within 5 minutes buffer)
                if datetime.now(timezone.utc) > (expiration - timedelta(minutes=5)):
                    # Credentials are expired, clear them from session
                    session.pop('assumed_credentials', None)
                    session.pop('assumed_role', None)
                    self.app.logger.warning("Session credentials have expired and were cleared")
                    # Fall through to ensure profile-based auth works

                else:
                    # Set environment variables for boto3 clients
                    os.environ['AWS_ACCESS_KEY_ID'] = creds['AccessKeyId']
                    os.environ['AWS_SECRET_ACCESS_KEY'] = creds['SecretAccessKey']
                    os.environ['AWS_SESSION_TOKEN'] = creds['SessionToken']
                    # Clear AWS_PROFILE to force use of env vars
                    if 'AWS_PROFILE' in os.environ:
                        # Store original profile for restoration later
                        if not hasattr(self.app, '_original_aws_profile'):
                            self.app._original_aws_profile = os.environ['AWS_PROFILE']
                        del os.environ['AWS_PROFILE']

                    # Debug logging
                    self.app.logger.info(f"ASSUMED ROLE ACTIVE: {session.get('assumed_role')} - using session credentials")
                    self.app.logger.debug(f"AWS_ACCESS_KEY_ID set: {os.environ.get('AWS_ACCESS_KEY_ID')[:10]}...")
                    return  # Don't set profile-based auth if assumed credentials are active

            # No assumed credentials or they were expired - ensure profile-based auth works
            if 'AWS_PROFILE' not in os.environ:
                os.environ['AWS_PROFILE'] = 'default'
                self.app.logger.info("NO ASSUMED ROLE: Using profile-based authentication (default)")
            else:
                self.app.logger.debug(f"Using existing AWS_PROFILE: {os.environ.get('AWS_PROFILE')}")

        @self.app.after_request
        def cleanup_after_request(response):
            """Clean up after request - restore AWS_PROFILE if needed"""
            # Only restore AWS_PROFILE if no session credentials are active AND no original credentials were stored
            if 'assumed_credentials' not in session and hasattr(self.app, '_original_aws_profile') and not self._original_credentials:
                if 'AWS_PROFILE' not in os.environ:
                    os.environ['AWS_PROFILE'] = self.app._original_aws_profile

            return response

    def set_assumed_credentials(self, credentials, role_name):
        """Store assumed credentials in session"""
        # Store original credentials BEFORE setting assumed credentials
        # This captures the base credentials used to assume the role
        # Only store if we haven't stored them before and if there are actual credentials
        if self._original_credentials is None:
            original_creds = {
                'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID'),
                'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY'),
                'AWS_SESSION_TOKEN': os.environ.get('AWS_SESSION_TOKEN'),
                'AWS_PROFILE': os.environ.get('AWS_PROFILE')
            }
            # Only store if we have at least some credentials (profile or keys)
            if (original_creds['AWS_PROFILE'] or
                (original_creds['AWS_ACCESS_KEY_ID'] and original_creds['AWS_SECRET_ACCESS_KEY'])):
                self._original_credentials = original_creds

        session['assumed_credentials'] = credentials
        session['assumed_role'] = role_name

        # Store original AWS_PROFILE for restoration
        if 'AWS_PROFILE' in os.environ and not hasattr(self.app, '_original_aws_profile'):
            self.app._original_aws_profile = os.environ['AWS_PROFILE']

    def clear_assumed_credentials(self):
        """Clear assumed credentials from session and restore base credentials"""
        self.app.logger.info(f"Clearing assumed credentials for role: {session.get('assumed_role')}")
        session.pop('assumed_credentials', None)
        session.pop('assumed_role', None)
        self.app.logger.info("Assumed credentials cleared from session")

        # Clear ALL AWS environment variables to ensure clean state
        aws_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN']
        for var in aws_vars:
            if var in os.environ:
                del os.environ[var]
                self.app.logger.debug(f"Cleared {var}")

        # Restore base credentials if they were stored originally
        if self._original_credentials:
            self.app.logger.info("Restoring original credentials")
            for key, value in self._original_credentials.items():
                if value is not None:
                    os.environ[key] = value
                    self.app.logger.debug(f"Restored {key}: {value[:10]}...")
        else:
            self.app.logger.info("No original credentials to restore - using profile-based auth only")

        # Always ensure AWS_PROFILE is set for profile-based authentication
        if hasattr(self.app, '_original_aws_profile'):
            os.environ['AWS_PROFILE'] = self.app._original_aws_profile
            self.app.logger.info(f"Restored AWS_PROFILE: {self.app._original_aws_profile}")
        elif 'AWS_PROFILE' not in os.environ:
            # If no profile was stored but we're using profile auth, set default
            os.environ['AWS_PROFILE'] = 'default'
            self.app.logger.info("Set AWS_PROFILE to default for profile-based auth")

    def get_session_info(self):
        """Get current session credential information"""
        if 'assumed_credentials' not in session:
            return {
                'session_credentials_active': False,
                'assumed_role': None,
                'credentials_expire': None
            }

        creds = session['assumed_credentials']
        expiration = datetime.fromisoformat(creds['Expiration'].replace('Z', '+00:00'))

        return {
            'session_credentials_active': True,
            'assumed_role': session.get('assumed_role'),
            'credentials_expire': expiration.isoformat()
        }

    def is_session_expired(self):
        """Check if session credentials are expired"""
        if 'assumed_credentials' not in session:
            return False

        creds = session['assumed_credentials']
        expiration = datetime.fromisoformat(creds['Expiration'].replace('Z', '+00:00'))

        # Return True if expired (within 5 minutes)
        return datetime.now(timezone.utc) > (expiration - timedelta(minutes=5))
