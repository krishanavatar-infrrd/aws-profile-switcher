import logging
import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

import json
import csv
from pymongo import MongoClient, errors

logger = logging.getLogger(__name__)


class MongoManager:
    """Handles MongoDB connections and collection access"""

    def __init__(self, connection_string: str, env_config: Optional[Dict[str, Any]] = None):
        self.connection_string = connection_string
        self.env_config = env_config or {}
        self.decrypt_fn = None

        try:
            self.client = MongoClient(
                connection_string,
                maxPoolSize=50,
                serverSelectionTimeoutMS=5000
            )
            # Verify connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")

            # Setup environment for decryption library if config is provided
            if self.env_config:
                self._setup_decryption_env()

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB or setup environment: {e}")
            raise

    def _setup_decryption_env(self):
        """Setup environment variables and initialize the core_db_encryption library.

        Key findings from reading the library source:
          - configs/base.py: MONGODB_DB_NAME defaults to "titanDB"
          - configs/base.py: Config.__init__ reads os.environ at instantiation time
          - configs/mongo_config.py: mongo_config = MongoConfig() is a module-level singleton
          - repository/mongo_client_connection.py: create_mongo_client() uses @lru_cache
          - repository/mongo_client_connection.py: check_db_existence() calls
            client.list_database_names() which requires cluster-wide auth — we must bypass this
          - __init__.py: calls load_dotenv() then imports decrypt
          - mongo_client_connection.py line 28: if MONGO_CONN_STR is set, uses it directly
        """
        conn_str = self.env_config.get('connect_string', '')

        # Extract host:port from connection string
        host_port = ''
        match = re.search(r'//(?:[^@]+@)?([^/?]+)', conn_str)
        if match:
            host_port = match.group(1)

        # Set the environment variables the library reads (from configs/base.py)
        os.environ['MONGODB_CONNECT'] = host_port
        os.environ['MONGODB_USERNAME'] = self.env_config.get('username', '')
        os.environ['MONGODB_PASSWORD'] = self.env_config.get('password', '')

        # MONGODB_DB_NAME is the critical var (defaults to "titanDB" in library)
        # Fall back to "titanDB" if user hasn't configured a default_database
        db_name = self.env_config.get('default_database', '') or 'titanDB'
        os.environ['MONGODB_DB_NAME'] = db_name

        # Also set MONGO_CONN_STR so the library reuses our authenticated connection string
        # instead of building its own from host/user/pass
        os.environ['MONGO_CONN_STR'] = conn_str

        logger.info(f"Set decryption env: MONGODB_CONNECT={host_port}, MONGODB_DB_NAME={db_name}, MONGO_CONN_STR=<set>")

        # Now import the library fresh so it picks up the new env vars
        try:
            # Purge all cached modules so Config() re-reads os.environ
            # and @lru_cache on create_mongo_client() starts fresh
            modules_to_remove = [m for m in sys.modules if m.startswith('core_db_encryption')]
            for mod_name in modules_to_remove:
                del sys.modules[mod_name]

            # Fresh import
            from core_db_encryption import decrypt

            # Monkey-patch check_db_existence to bypass list_database_names()
            # The library calls this which requires cluster-wide listDatabases permission.
            # We know the database exists (the user configured it), so we just return True.
            from core_db_encryption.repository.mongo_client_connection import MongoTemplate
            MongoTemplate.check_db_existence = staticmethod(lambda db_name, client: True)

            self.decrypt_fn = decrypt
            logger.info("Successfully initialized core_db_encryption (check_db_existence bypassed)")
        except ImportError:
            logger.warning("core_db_encryption library not found. Decryption will be skipped.")
        except Exception as e:
            logger.error(f"Error initializing core_db_encryption: {e}")

    def get_databases(self) -> List[str]:
        """List all databases"""
        return self.client.list_database_names()

    def get_collections(self, db_name: str) -> List[str]:
        """List all collections in a database"""
        try:
            return self.client[db_name].list_collection_names()
        except Exception as e:
            logger.warning(f"Failed to list collections for {db_name}: {e}")
            return []

    def query(self, db_name: str, collection_name: str,
              query_dict: Dict[str, Any],
              projection_dict: Optional[Dict[str, Any]] = None,
              sort_dict: Optional[List[tuple]] = None,
              limit: int = 100,
              skip: int = 0,
              is_encrypted: bool = False) -> Dict[str, Any]:
        """Perform a query and optionally decrypt results"""
        db = self.client[db_name]
        collection = db[collection_name]

        # Get total count for the query
        try:
            total_count = collection.count_documents(query_dict)
        except Exception as e:
            logger.warning(f"Could not get document count: {e}")
            total_count = 0

        # Ensure "isEncrypted" is fetched if decryption is requested
        actual_projection = projection_dict
        if is_encrypted and projection_dict:
            actual_projection = projection_dict.copy()
            actual_projection["isEncrypted"] = 1

        cursor = collection.find(query_dict, actual_projection)

        if sort_dict:
            cursor = cursor.sort(sort_dict)

        if skip > 0:
            cursor = cursor.skip(skip)

        if limit > 0:
            cursor = cursor.limit(limit)

        results = list(cursor)

        if is_encrypted and self.decrypt_fn:
            try:
                results = self.decrypt_fn(results, collection_name)
            except Exception as e:
                logger.error(f"Decryption failed: {e}")

        return {
            "results": [self._serialize_doc(doc) for doc in results],
            "total_count": total_count
        }

    def export_data(self, db_name: str, collection_name: str,
                    query_dict: Dict[str, Any],
                    format: str,
                    export_path: str,
                    projection_dict: Optional[Dict[str, Any]] = None,
                    sort_dict: Optional[List[tuple]] = None,
                    limit: int = 0,
                    is_encrypted: bool = False) -> Dict[str, Any]:
        """Query data and export to local file (JSON or CSV)"""
        db = self.client[db_name]
        collection = db[collection_name]

        # Handle projection for decryption
        actual_projection = projection_dict
        if is_encrypted and projection_dict:
            actual_projection = projection_dict.copy()
            actual_projection["isEncrypted"] = 1

        cursor = collection.find(query_dict, actual_projection)

        if sort_dict:
            cursor = cursor.sort(sort_dict)

        if limit > 0:
            cursor = cursor.limit(limit)

        results = list(cursor)

        if is_encrypted and self.decrypt_fn:
            try:
                results = self.decrypt_fn(results, collection_name)
            except Exception as e:
                logger.error(f"Decryption failed during export: {e}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(export_path), exist_ok=True)

        if format.lower() == 'json':
            serialized_results = [self._serialize_doc(doc) for doc in results]
            with open(export_path, 'w') as f:
                json.dump(serialized_results, f, indent=2)
        elif format.lower() == 'csv':
            if not results:
                # Create empty file or header only
                with open(export_path, 'w', newline='') as f:
                    pass
            else:
                flattened_results = [self._flatten_dict(self._serialize_doc(doc)) for doc in results]
                # Get all unique keys for header
                keys = set()
                for doc in flattened_results:
                    keys.update(doc.keys())
                keys = sorted(list(keys))

                with open(export_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(flattened_results)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return {
            "success": True,
            "count": len(results),
            "export_path": export_path
        }

    def _serialize_doc(self, data):
        """Recursively convert MongoDB types to JSON serializable formats"""
        if isinstance(data, list):
            return [self._serialize_doc(item) for item in data]
        if isinstance(data, dict):
            return {k: self._serialize_doc(v) for k, v in data.items()}
        if isinstance(data, datetime):
            return data.isoformat()

        try:
            from bson import ObjectId
            if isinstance(data, ObjectId):
                return str(data)
        except ImportError:
            pass

        if hasattr(data, '__str__') and not isinstance(data, (int, float, bool, str, type(None))):
            return str(data)

        return data

    @staticmethod
    def _flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten a nested dictionary for CSV export"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(MongoManager._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def close(self):
        """Close MongoDB connection"""
        self.client.close()
