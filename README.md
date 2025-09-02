# AWS Profile Manager Flask Application

A web-based interface for managing AWS profiles and credentials, built with Flask and Bootstrap.

## Features

- **Dashboard**: Overview of current profile, environment, and credentials status
- **Profile Management**: Create, switch, and remove AWS profiles (both credentials and role-based)
- **Environment Management**: Switch between different AWS environments (dev, stage, prod, etc.)
- **Credentials Management**: Sync credentials from base file, refresh, and clean configuration
- **Real-time Status**: Live updates of profile and environment status

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure the original `aws_profile_switcher.py` file is in the same directory

3. Run the Flask application:
```bash
python aws_profile_manager_flask.py
```

4. Open your browser and navigate to: `http://localhost:5000`

## Usage

### Dashboard
- View current profile and environment status
- Quick actions for common tasks
- Environment switching with one click

### Profiles
- Create new credentials profiles with AWS keys
- Create role-based profiles for assuming roles
- Switch between profiles
- Remove unwanted profiles

### Environments
- View all available environments
- Switch between environments (dev, stage, prod, etc.)
- See current environment configuration

### Credentials
- Monitor credentials status across all files
- Sync credentials from base file
- Force refresh and clean configuration
- View detailed status of all credential components

## File Structure

```
SWBC/boto/
├── aws_profile_switcher.py          # Original CLI script
├── aws_profile_manager_flask.py     # Flask application
├── requirements.txt                 # Python dependencies
├── templates/                       # HTML templates
│   ├── base.html                   # Base template
│   ├── index.html                  # Dashboard
│   ├── profiles.html               # Profile management
│   ├── environments.html           # Environment management
│   └── credentials.html            # Credentials management
└── README.md                       # This file
```

## API Endpoints

- `GET /` - Dashboard
- `GET /profiles` - Profile management page
- `GET /environments` - Environment management page
- `GET /credentials` - Credentials management page
- `POST /api/switch_profile` - Switch to a different profile
- `POST /api/switch_environment` - Switch to a different environment
- `POST /api/sync_credentials` - Sync credentials from base file
- `POST /api/force_refresh` - Force refresh credentials
- `POST /api/clean_config` - Clean configuration file
- `POST /api/force_clean_reset` - Force clean and reset
- `POST /api/update_credentials` - Update profile credentials
- `POST /api/create_role_profile` - Create role-based profile
- `POST /api/remove_profile` - Remove a profile
- `GET /api/status` - Get current status

## Configuration

The application uses the same configuration as the original CLI script:
- Base credentials file: `/home/krishnavatar/Downloads/credentials`
- AWS credentials file: `~/.aws/credentials`
- AWS config file: `~/.aws/config`

## Security Note

This application runs on `0.0.0.0:5000` by default, making it accessible from any network interface. For production use, consider:
- Running behind a reverse proxy
- Adding authentication
- Using HTTPS
- Restricting network access
