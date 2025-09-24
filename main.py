#!/usr/bin/env python3
"""
Main entry point for AWS Profile Manager
"""

import sys
import argparse
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))

from aws_profile_manager.cli import main as cli_main
from aws_profile_manager.api.flask_app import run_app


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='AWS Profile Manager')
    parser.add_argument('--web', action='store_true', help='Start web interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host for web interface')
    parser.add_argument('--port', type=int, default=5000, help='Port for web interface')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('command', nargs='*', help='CLI command and arguments')

    args = parser.parse_args()

    if args.web:
        print(f"🚀 Starting AWS Profile Manager Web Interface...")
        print(f"📱 Access it at: http://{args.host}:{args.port}")
        run_app(host=args.host, port=args.port, debug=args.debug)
    else:
        # Run CLI
        if args.command:
            sys.argv = ['aws_profile_manager'] + args.command
        cli_main()


if __name__ == '__main__':
    main()
