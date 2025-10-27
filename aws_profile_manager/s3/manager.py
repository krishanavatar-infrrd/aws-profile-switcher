"""
S3 Operations Management
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from aws_profile_manager.utils.logging import LoggerMixin


class S3Manager(LoggerMixin):
    """Manages S3 operations like listing buckets, objects, and downloading files"""
    
    def __init__(self):
        if not BOTO3_AVAILABLE:
            self.logger.warning("boto3 is not available. S3 operations will not work.")
    
    def _create_s3_client(self):
        """Create S3 client with proper credential handling"""
        # Check if we have explicit credentials in environment variables (assumed role)
        if 'AWS_ACCESS_KEY_ID' in os.environ and 'AWS_SECRET_ACCESS_KEY' in os.environ:
            self.logger.debug("Creating S3 client with explicit credentials from environment")
            return boto3.client('s3',
                              aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                              aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                              aws_session_token=os.environ.get('AWS_SESSION_TOKEN'),
                              region_name='us-east-1',
                              config=boto3.session.Config(signature_version='s3v4'))
        else:
            self.logger.debug("Creating S3 client with profile-based credentials")
            return boto3.client('s3',
                              region_name='us-east-1',
                              config=boto3.session.Config(signature_version='s3v4'))
    
    def _create_sts_client(self):
        """Create STS client with proper credential handling"""
        # Check if we have explicit credentials in environment variables (assumed role)
        if 'AWS_ACCESS_KEY_ID' in os.environ and 'AWS_SECRET_ACCESS_KEY' in os.environ:
            self.logger.debug("Creating STS client with explicit credentials from environment")
            return boto3.client('sts',
                              aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                              aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                              aws_session_token=os.environ.get('AWS_SESSION_TOKEN'),
                              region_name='us-east-1',
                              config=boto3.session.Config(signature_version='s3v4'))
        else:
            self.logger.debug("Creating STS client with profile-based credentials")
            return boto3.client('sts',
                              region_name='us-east-1',
                              config=boto3.session.Config(signature_version='s3v4'))
    
    def list_buckets(self) -> Dict[str, Union[bool, str, List[Dict]]]:
        """List all S3 buckets"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            # Create S3 client with proper credential handling
            s3_client = self._create_s3_client()

            # Debug: Check what credentials the client is using
            try:
                sts_client = self._create_sts_client()
                identity = sts_client.get_caller_identity()
                self.logger.info(f"S3 client using account: {identity.get('Account')}, user: {identity.get('UserId')}")
            except Exception as e:
                self.logger.warning(f"Could not get caller identity for S3: {e}")

            response = s3_client.list_buckets()

            buckets = []
            for bucket in response['Buckets']:
                buckets.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].isoformat()
                })

            return {
                'success': True,
                'buckets': buckets,
                'can_list_all_buckets': True
            }

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            # Handle specific case where user doesn't have ListAllMyBuckets permission
            if error_code == 'AccessDenied' and 'ListAllMyBuckets' in error_message:
                return {
                    'success': True,  # Still success, but limited
                    'buckets': [],
                    'can_list_all_buckets': False,
                    'message': 'Permission denied: Cannot list all S3 buckets. This role may only have access to specific buckets. You can manually enter a bucket name to access it.',
                    'permission_error': True
                }
            else:
                return {
                    'success': False,
                    'message': f"AWS Error: {error_code} - {error_message}"
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def check_bucket_access(self, bucket_name: str) -> Dict[str, Union[bool, str]]:
        """Check if a bucket exists and is accessible"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            s3_client = self._create_s3_client()

            # Try to get bucket location (this will fail if bucket doesn't exist or isn't accessible)
            try:
                response = s3_client.get_bucket_location(Bucket=bucket_name)
                location = response.get('LocationConstraint', 'us-east-1')
                if location is None:  # us-east-1 buckets return None
                    location = 'us-east-1'

                return {
                    'success': True,
                    'accessible': True,
                    'bucket_name': bucket_name,
                    'region': location,
                    'message': f'Bucket "{bucket_name}" is accessible in region {location}'
                }

            except ClientError as e:
                error_code = e.response['Error']['Code']

                if error_code == 'NoSuchBucket':
                    return {
                        'success': True,
                        'accessible': False,
                        'bucket_name': bucket_name,
                        'message': f'Bucket "{bucket_name}" does not exist or is not accessible'
                    }
                elif error_code == 'AccessDenied':
                    return {
                        'success': True,
                        'accessible': False,
                        'bucket_name': bucket_name,
                        'message': f'Access denied to bucket "{bucket_name}". You may not have permission to access this bucket.'
                    }
                else:
                    return {
                        'success': False,
                        'message': f"AWS Error checking bucket: {error_code} - {e.response['Error']['Message']}"
                    }

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def list_objects(self, bucket_name: str, prefix: str = '', max_keys: int = 20, continuation_token: str = None) -> Dict[str, Union[bool, str, List[Dict], str]]:
        """List objects in an S3 bucket with pagination"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            s3_client = self._create_s3_client()

            list_params = {
                'Bucket': bucket_name,
                'MaxKeys': max_keys,
                'Delimiter': '/'
            }
            
            if prefix:
                list_params['Prefix'] = prefix
            
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
            
            response = s3_client.list_objects_v2(**list_params)
            
            objects = []
            folders = []
            
            # Process folders (CommonPrefixes)
            if 'CommonPrefixes' in response:
                for prefix_obj in response['CommonPrefixes']:
                    folder_name = prefix_obj['Prefix']
                    # Remove trailing slash for display
                    display_name = folder_name.rstrip('/')
                    folder_path = folder_name
                    folders.append({
                        'name': display_name,
                        'type': 'folder',
                        'path': folder_path
                    })

            # Process objects
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip the prefix itself if it's an object
                    if obj['Key'] == prefix:
                        continue

                    obj_key = obj['Key']
                    obj_name = obj['Key'].split('/')[-1]

                    # Check if this is a folder-like object (ends with / and size 0)
                    if obj_name == '' and obj['Size'] == 0 and obj_key.endswith('/'):
                        # This is a folder marker object
                        folder_name = obj_key
                        display_name = obj_key.rstrip('/').split('/')[-1] if '/' in obj_key.rstrip('/') else obj_key.rstrip('/')
                        if not any(f['path'] == folder_name for f in folders):
                            folders.append({
                                'name': display_name,
                                'type': 'folder',
                                'path': folder_name
                            })
                    else:
                        # This is a regular file
                        objects.append({
                            'name': obj_name,
                            'key': obj_key,
                            'type': 'file',
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'etag': obj['ETag'].strip('"')
                        })
            
            result = {
                'success': True,
                'objects': objects,
                'folders': folders,
                'bucket': bucket_name,
                'prefix': prefix,
                'is_truncated': response.get('IsTruncated', False)
            }
            
            if response.get('NextContinuationToken'):
                result['next_continuation_token'] = response['NextContinuationToken']
            
            return result
            
        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    def download_file(self, bucket_name: str, object_key: str, local_path: str) -> Dict[str, Union[bool, str]]:
        """Download a file from S3"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            s3_client = self._create_s3_client()

            # Create local directory if it doesn't exist
            local_file_path = Path(local_path)
            local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file
            s3_client.download_file(bucket_name, object_key, str(local_file_path))
            
            self.logger.info(f"Downloaded {object_key} to {local_path}")
            
            return {
                'success': True,
                'message': f'File downloaded successfully to {local_path}'
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    def upload_file(self, local_path: str, bucket_name: str, object_key: str) -> Dict[str, Union[bool, str]]:
        """Upload a file to S3"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            s3_client = self._create_s3_client()

            # Upload the file
            s3_client.upload_file(local_path, bucket_name, object_key)
            
            self.logger.info(f"Uploaded {local_path} to s3://{bucket_name}/{object_key}")
            
            return {
                'success': True,
                'message': f'File uploaded successfully to s3://{bucket_name}/{object_key}'
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    def delete_object(self, bucket_name: str, object_key: str) -> Dict[str, Union[bool, str]]:
        """Delete an object from S3"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            s3_client = self._create_s3_client()

            # Delete the object
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)

            self.logger.info(f"Deleted s3://{bucket_name}/{object_key}")

            return {
                'success': True,
                'message': f'Object deleted successfully: s3://{bucket_name}/{object_key}'
            }

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def get_credential_info(self) -> Dict[str, Union[bool, str, Dict]]:
        """Get information about current AWS credentials being used"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            # Check if session token is present (indicates assumed role)
            has_session_token = bool(os.environ.get('AWS_SESSION_TOKEN'))

            # Try to get caller identity, but handle expired tokens gracefully
            try:
                sts_client = self._create_sts_client()
                identity = sts_client.get_caller_identity()
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ExpiredToken':
                    # Credentials are expired, return basic info
                    self.logger.info("Assumed role credentials have expired")
                    return {
                        'success': True,
                        'account_id': 'Unknown (expired)',
                        'user_id': 'Unknown (expired)',
                        'arn': 'Unknown (expired)',
                        'is_assumed_role': has_session_token,
                        'region': 'us-east-1',
                        'expired': True,
                        'message': 'Credentials have expired'
                    }
                elif error_code == 'AccessDenied':
                    # No STS permissions, return basic info
                    return {
                        'success': True,
                        'account_id': 'Unknown (no STS access)',
                        'user_id': 'Unknown (no STS access)',
                        'arn': 'Unknown (no STS access)',
                        'is_assumed_role': has_session_token,
                        'region': 'us-east-1',
                        'no_sts_access': True,
                        'message': 'No STS permissions available'
                    }
                else:
                    # Re-raise other errors
                    raise e

            credential_info = {
                'success': True,
                'account_id': identity.get('Account'),
                'user_id': identity.get('UserId'),
                'arn': identity.get('Arn'),
                'is_assumed_role': has_session_token,
                'region': 'us-east-1'
            }

            # Extract role name if it's an assumed role
            if has_session_token and 'assumed-role' in identity.get('Arn', ''):
                # ARN format: arn:aws:sts::account:assumed-role/role-name/session-name
                arn_parts = identity.get('Arn', '').split('/')
                if len(arn_parts) >= 2:
                    credential_info['role_name'] = arn_parts[1]

            return credential_info

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def search_object_by_path(self, bucket_name: str, object_key: str) -> Dict[str, Union[bool, str, Dict]]:
        """Search for a specific object by complete path"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            s3_client = self._create_s3_client()

            # Try to get object metadata (this will fail if object doesn't exist)
            try:
                response = s3_client.head_object(Bucket=bucket_name, Key=object_key)

                # Object exists, return its details
                object_info = {
                    'success': True,
                    'found': True,
                    'bucket': bucket_name,
                    'key': object_key,
                    'size': response.get('ContentLength', 0),
                    'last_modified': response.get('LastModified').isoformat() if response.get('LastModified') else None,
                    'etag': response.get('ETag', '').strip('"'),
                    'content_type': response.get('ContentType', ''),
                    'storage_class': response.get('StorageClass', 'STANDARD')
                }

                return object_info

            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Object doesn't exist
                    return {
                        'success': True,
                        'found': False,
                        'bucket': bucket_name,
                        'key': object_key,
                        'message': f'Object s3://{bucket_name}/{object_key} not found'
                    }
                else:
                    # Some other error
                    raise e

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }

    def get_presigned_download_url(self, bucket_name: str, object_key: str, expiration: int = 3600) -> Dict[str, Union[bool, str]]:
        """Generate a presigned URL for downloading an S3 object"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }

        try:
            s3_client = self._create_s3_client()

            # Generate presigned URL
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expiration
            )

            return {
                'success': True,
                'presigned_url': presigned_url,
                'expiration_seconds': expiration,
                'bucket': bucket_name,
                'key': object_key
            }

        except NoCredentialsError:
            return {
                'success': False,
                'message': 'No AWS credentials found. Please configure your credentials first.'
            }
        except ClientError as e:
            return {
                'success': False,
                'message': f"AWS Error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
