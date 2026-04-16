"""
EFS (SFTP) Operations Management
"""

import os
import paramiko
import stat
from datetime import datetime
from typing import Dict, List, Optional, Union
from pathlib import Path

from aws_profile_manager.utils.logging import LoggerMixin


class SFTPHandler:
    """Robust SFTP client handler using paramiko"""
    def __init__(self, host: str, port: int = 22, username: str = 'filereader', private_key: str | None = None):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.load_system_host_keys()
        
        try:
            connect_kwargs = {
                'hostname': host,
                'port': port,
                'username': username,
                'timeout': 15,
                'allow_agent': True,
                'look_for_keys': True
            }
            
            if private_key and os.path.exists(private_key):
                connect_kwargs['key_filename'] = private_key
                
            self.ssh_client.connect(**connect_kwargs)
            self.sftp_client = self.ssh_client.open_sftp()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {host}: {str(e)}")

    def close(self):
        if hasattr(self, 'sftp_client') and self.sftp_client:
            self.sftp_client.close()
        if hasattr(self, 'ssh_client') and self.ssh_client:
            self.ssh_client.close()


class EFSManager(LoggerMixin):
    """Manages EFS operations via SFTP (SSH)"""
    
    def __init__(self):
        self._handler = None
    
    def _get_handler(self, config: Dict) -> SFTPHandler:
        """Create a new SFTP handler from config"""
        host = config.get('host')
        username = config.get('username')
        key_path = config.get('key_path')
        port = int(config.get('port', 22))
        
        return SFTPHandler(host, port, username, key_path)

    def list_files(self, config: Dict, remote_path: str = '.') -> Dict[str, Union[bool, str, List[Dict]]]:
        """List files in a directory via SFTP"""
        handler = None
        try:
            handler = self._get_handler(config)
            sftp = handler.sftp_client
            
            # Normalize path
            if not remote_path or remote_path == '.':
                remote_path = sftp.normalize('.')
            
            # Check if path exists/is directory
            try:
                file_attr = sftp.stat(remote_path)
                if not stat.S_ISDIR(file_attr.st_mode):
                    # If it's a file, return just this file
                    name = os.path.basename(remote_path)
                    item = {
                        'name': name,
                        'path': remote_path,
                        'type': 'file',
                        'size': file_attr.st_size,
                        'last_modified': datetime.fromtimestamp(file_attr.st_mtime).isoformat(),
                        'permissions': stat.filemode(file_attr.st_mode)
                    }
                    return {
                        'success': True,
                        'objects': [item],
                        'folders': [],
                        'current_path': remote_path,
                        'is_search': False
                    }
            except FileNotFoundError:
                 return {'success': False, 'message': f'Path {remote_path} not found'}

            objects = []
            folders = []
            
            for entry in sftp.listdir_attr(remote_path):
                name = entry.filename
                if name in ['.', '..']:
                    continue
                    
                full_path = os.path.join(remote_path, name)
                is_dir = stat.S_ISDIR(entry.st_mode)
                
                item = {
                    'name': name,
                    'path': full_path,
                    'type': 'folder' if is_dir else 'file',
                    'size': entry.st_size,
                    'last_modified': datetime.fromtimestamp(entry.st_mtime).isoformat(),
                    'permissions': stat.filemode(entry.st_mode)
                }
                
                if is_dir:
                    folders.append(item)
                else:
                    objects.append(item)
            
            folders.sort(key=lambda x: x['name'].lower())
            objects.sort(key=lambda x: x['name'].lower())

            return {
                'success': True,
                'objects': objects,
                'folders': folders,
                'current_path': remote_path
            }
        except Exception as e:
            self.logger.error(f"Error listing files: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def search_files(self, config: Dict, search_term: str, remote_path: str = '.') -> Dict[str, Union[bool, str, List[Dict]]]:
        """Search files in EFS recursively"""
        handler = None
        try:
            handler = self._get_handler(config)
            sftp = handler.sftp_client
            
            if not remote_path or remote_path == '.':
                remote_path = sftp.normalize('.')

            results = []
            
            def _recursive_search(current_dir):
                try:
                    for entry in sftp.listdir_attr(current_dir):
                        name = entry.filename
                        if name in ['.', '..']:
                            continue
                        
                        full_path = os.path.join(current_dir, name)
                        is_dir = stat.S_ISDIR(entry.st_mode)
                        
                        if search_term.lower() in name.lower():
                            item = {
                                'name': name,
                                'path': full_path,
                                'type': 'folder' if is_dir else 'file',
                                'size': entry.st_size,
                                'last_modified': datetime.fromtimestamp(entry.st_mtime).isoformat(),
                                'permissions': stat.filemode(entry.st_mode)
                            }
                            results.append(item)
                        
                        if is_dir:
                            _recursive_search(full_path)
                except Exception as e:
                    self.logger.warning(f"Error searching in {current_dir}: {e}")

            _recursive_search(remote_path)
            
            return {
                'success': True,
                'objects': [r for r in results if r['type'] == 'file'],
                'folders': [r for r in results if r['type'] == 'folder'],
                'current_path': remote_path,
                'is_search': True
            }
        except Exception as e:
            self.logger.error(f"Error searching files: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def download_file(self, config: Dict, remote_path: str, local_path: str = None) -> Dict[str, Union[bool, str]]:
        """Download file from SFTP"""
        handler = None
        try:
            handler = self._get_handler(config)
            if not local_path:
                import tempfile
                local_path = os.path.join(tempfile.gettempdir(), os.path.basename(remote_path))

            handler.sftp_client.get(remote_path, local_path)
            return {'success': True, 'message': 'File downloaded successfully', 'local_path': local_path}
        except Exception as e:
            self.logger.error(f"Error downloading file: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def archive_folder(self, config: Dict, remote_path: str) -> Dict[str, Union[bool, str]]:
        """Create a ZIP archive of a remote folder and download it"""
        handler = None
        try:
            handler = self._get_handler(config)
            sftp = handler.sftp_client
            import tempfile, zipfile
            
            local_zip_path = os.path.join(tempfile.gettempdir(), f"{os.path.basename(remote_path)}.zip")
            
            with zipfile.ZipFile(local_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                def _add_to_zip(current_remote_path, current_arc_path):
                    for entry in sftp.listdir_attr(current_remote_path):
                        name = entry.filename
                        if name in ['.', '..']: continue
                        
                        remote_item_path = os.path.join(current_remote_path, name)
                        arc_item_path = os.path.join(current_arc_path, name)
                        
                        if stat.S_ISDIR(entry.st_mode):
                            _add_to_zip(remote_item_path, arc_item_path)
                        else:
                            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                                sftp.get(remote_item_path, tmp.name)
                                zipf.write(tmp.name, arc_item_path)
                                os.unlink(tmp.name)
                
                _add_to_zip(remote_path, os.path.basename(remote_path))
            
            return {'success': True, 'message': 'Folder archived successfully', 'local_path': local_zip_path}
        except Exception as e:
            self.logger.error(f"Error archiving folder: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def download_recursive(self, config: Dict, remote_path: str, local_dest_dir: str) -> Dict[str, Union[bool, str]]:
        """Download a folder recursively from SFTP to local filesystem"""
        handler = None
        try:
            handler = self._get_handler(config)
            sftp = handler.sftp_client
            
            # Normalize remote path
            remote_path = sftp.normalize(remote_path)
            self.logger.info(f"Starting recursive download: {remote_path} -> {local_dest_dir}")
            
            def _download_dir(remote_dir, local_dir):
                self.logger.info(f"Downloading directory: {remote_dir}")
                if not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)
                
                entries = sftp.listdir_attr(remote_dir)
                self.logger.info(f"Found {len(entries)} items in {remote_dir}")
                
                for entry in entries:
                    name = entry.filename
                    if name in ['.', '..']: continue
                    
                    # Use forward slashes for SFTP
                    remote_item = remote_dir.rstrip('/') + '/' + name
                    local_item = os.path.join(local_dir, name)
                    
                    if stat.S_ISDIR(entry.st_mode):
                        _download_dir(remote_item, local_item)
                    else:
                        self.logger.info(f"Downloading file: {remote_item}")
                        sftp.get(remote_item, local_item)
            
            _download_dir(remote_path, local_dest_dir)
            return {'success': True, 'message': f'Successfully downloaded to {local_dest_dir}', 'local_path': local_dest_dir}
        except Exception as e:
            self.logger.error(f"Error recursive download: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def upload_file(self, config: Dict, local_path: str, remote_dir: str) -> Dict[str, Union[bool, str]]:
        """Upload file via SFTP"""
        handler = None
        try:
            handler = self._get_handler(config)
            if not os.path.exists(local_path):
                 return {'success': False, 'message': f'Local file {local_path} not found'}

            filename = os.path.basename(local_path)
            remote_path = os.path.join(remote_dir, filename)
            handler.sftp_client.put(local_path, remote_path)
            return {'success': True, 'message': f'File uploaded successfully to {remote_path}'}
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()

    def delete_file(self, config: Dict, remote_path: str) -> Dict[str, Union[bool, str]]:
        """Delete file or directory via SFTP"""
        handler = None
        try:
            handler = self._get_handler(config)
            sftp = handler.sftp_client
            
            file_attr = sftp.stat(remote_path)
            if stat.S_ISDIR(file_attr.st_mode):
                def _recursive_delete(path):
                    for entry in sftp.listdir_attr(path):
                        item_path = os.path.join(path, entry.filename)
                        if stat.S_ISDIR(entry.st_mode):
                            _recursive_delete(item_path)
                        else:
                            sftp.remove(item_path)
                    sftp.rmdir(path)
                _recursive_delete(remote_path)
            else:
                sftp.remove(remote_path)
                
            return {'success': True, 'message': f'Item {remote_path} deleted successfully'}
        except Exception as e:
            self.logger.error(f"Error deleting file: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if handler:
                handler.close()
