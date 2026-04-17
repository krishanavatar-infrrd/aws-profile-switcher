# AWS Profile Manager & Utility Suite

A comprehensive web-based interface for managing AWS profiles, S3 buckets, remote EFS/SFTP file browsing, and MongoDB query/export utilities. Built with Flask, Bootstrap 5, and Boto3.

## 🚀 Key Modules

### 🛠 AWS Profile & Environment Management
- **Profile Switching**: Easily toggle between named AWS profiles (credentials or role-based).
- **Environment Context**: Switch between Dev, Stage, and Prod account contexts with a single click.
- **Credential Sync**: Automated synchronization of temporary credentials from a base source file.
- **Assume Role Integration**: Support for External IDs, Session Names, and custom durations.

### ☁️ S3 Management
- **Multi-Bucket Browsing**: Predefined bucket shortcuts and dynamic bucket access.
- **File Browser**: Cyberduck-like navigation through S3 paths.
- **Downloads/Uploads**: Integrated file management directly from the web UI.

### 📁 SFTP / EFS Management
- **Remote Browsing**: Secure SFTP connection profiles for managing remote EFS contents.
- **Recursive Downloads**: Folder-level downloads that preserve structure.
- **MongoDB Lookup Integration**: Automatically navigate to a file path based on a MongoDB Document ID or Request ID from `titanDB`.

### 🍃 MongoDB Utility
- **Multi-Environment Support**: Connect to Stage, UAT, and Prod MongoDB instances.
- **Dynamic Browsing**: Browse Databases and Collections with ease.
- **Advanced Querying**: Filter results using JSON, apply projections, sort, and limit results.
- **Data Export**: Export query results directly to **JSON** or **CSV**.
- **State Persistence**: Your last selected Environment, Database, Collection, and Query are automatically remembered.
- **Encryption Support**: Toggle automated decryption for sensitive fields.

---

## 🛠 Setup & Installation

### Prerequisites
- Python 3.8 or higher
- `pip` (Python package manager)
- AWS CLI configured (for `~/.aws/` files)

### 1. Clone & Prepare Environment
```bash
# Clone the repository
git clone <repo-url>
cd aws-profile-switcher

# Create a virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Mac/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`config.json`)
The application is controlled by `config.json`. You can customize:
- `base_credentials_path`: Point this to your source credentials file (e.g., `~/Downloads/credentials`).
- `environments`: Define your AWS Account IDs and Roles.
- `efs_connections`: Define your SFTP hosts and usernames.
- `mongo_configs`: Define your MongoDB connection strings.

### 3. Environment Variables
Ensure the following variables are set in your shell (e.g., `.zshrc` or `.bashrc`):
```bash
# MongoDB Credentials
export MONGODB_CONNECT="true"
export MONGODB_USERNAME="your-username"
export MONGODB_PASSWORD="your-password"
export MONGO_CONN_STR="your-connection-string"
export MONGODB_DB_NAME="titanDB"
```

### 4. Running the Application
```bash
# Run the main entry point
python main.py
```
Default access: [http://localhost:5000](http://localhost:5000)

---

## 💡 Troubleshooting & Notes

### MongoDB Decryption
If the **Decrypt** feature in the MongoDB Utility is not working as expected, you may need to patch the `core_db_encryption` library within your virtual environment.
- **File**: `.venv/lib/python3.*/site-packages/core_db_encryption/repository/mongo_client_connection.py`
- **Change**: In the `MongoClient` instantiation, ensure `directConnection=True` is included:
```python
return MongoClient(
    host=mongo_config.mongo_host,
    ...
    connect=True,
    directConnection=True, # Add this line
    w=w
)
```

---

## 🏗 Bedrock Integration
The project includes a `bedrock.sh` script in the root directory. 
- This script is used to configure environment variables for AWS Bedrock integration.
- **Customization**: Open [bedrock.sh](file:///Users/krishnavatar/personal_projects/aws-profile-switcher/bedrock.sh) to update your preferred `AWS_REGION` or to enable/disable specific model overrides.
- The web interface will automatically manage the sourcing of this script in your shell profile (`.zshrc`, `.bashrc`, or `.bash_profile`) when toggling Bedrock features.

---

## 💻 OS Specific Notes

### Mac vs Linux
- **Path Resolution**: The app uses `os.path.expanduser` to resolve `~/` paths, ensuring compatibility between macOS and standard Linux distros.
- **Downloads**: By default, the Mongo Utility suggests `~/Downloads/` for exports. Ensure this directory exists or update it in the UI.
- **Credentials**: Standard AWS pathing (`~/.aws/credentials`) is used across both platforms.

---

## 🔒 Security Note
This application is designed for local developer productivity. 
- It binds to `0.0.0.0` by default. 
- Avoid exposing the port on public networks.
- Manage your sensitive connection strings in `config.json` carefully.
