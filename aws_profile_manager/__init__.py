"""
AWS Profile Manager Package

A comprehensive tool for managing AWS profiles, credentials, environments, and S3 operations.
"""

from aws_profile_manager.core.manager import AWSProfileManager
from aws_profile_manager.core.config import ConfigManager
from aws_profile_manager.aws.credentials import AWSCredentialsManager
from aws_profile_manager.aws.environments import EnvironmentManager
from aws_profile_manager.roles.assume_role import AWSRoleManager
from aws_profile_manager.s3.manager import S3Manager
from aws_profile_manager.utils.logging import setup_logging, get_logger

__version__ = "1.0.0"
__author__ = "AWS Profile Manager Team"
__description__ = "A comprehensive AWS profile and credentials management tool"

__all__ = [
    'AWSProfileManager',
    'ConfigManager',
    'AWSCredentialsManager',
    'EnvironmentManager',
    'AWSRoleManager',
    'S3Manager',
    'setup_logging',
    'get_logger'
]
