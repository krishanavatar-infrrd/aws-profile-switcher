"""
S3 Operations Management
"""

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
    
    def list_buckets(self) -> Dict[str, Union[bool, str, List[Dict]]]:
        """List all S3 buckets"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            s3_client = boto3.client('s3')
            response = s3_client.list_buckets()
            
            buckets = []
            for bucket in response['Buckets']:
                buckets.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].isoformat()
                })
            
            return {
                'success': True,
                'buckets': buckets
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
    
    def list_objects(self, bucket_name: str, prefix: str = '', max_keys: int = 20, continuation_token: str = None) -> Dict[str, Union[bool, str, List[Dict], str]]:
        """List objects in an S3 bucket with pagination"""
        if not BOTO3_AVAILABLE:
            return {
                'success': False,
                'message': 'boto3 is not available. Please install it with: pip install boto3'
            }
        
        try:
            s3_client = boto3.client('s3')
            
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
                    folders.append({
                        'name': folder_name,
                        'type': 'folder',
                        'path': folder_name
                    })
            
            # Process objects
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip the prefix itself if it's an object
                    if obj['Key'] == prefix:
                        continue
                    
                    objects.append({
                        'name': obj['Key'].split('/')[-1],
                        'key': obj['Key'],
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
            s3_client = boto3.client('s3')
            
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
            s3_client = boto3.client('s3')
            
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
            s3_client = boto3.client('s3')
            
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
