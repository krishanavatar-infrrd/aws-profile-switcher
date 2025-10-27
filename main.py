#!/usr/bin/env python3
"""
Main entry point for AWS Profile Manager Web Interface
"""

import sys
import argparse
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))

from aws_profile_manager.api.flask_app import run_app


def main():
    """Main entry point - Always starts web interface"""
    parser = argparse.ArgumentParser(description='AWS Profile Manager Web Interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host for web interface (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port for web interface (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    print(f"🚀 Starting AWS Profile Manager Web Interface...")
    print(f"📱 Access it at: http://{args.host}:{args.port}")
    print(f"🔧 Debug mode: {'ON' if args.debug else 'OFF'}")
    print(f"\n💡 For CLI commands, use: python -m aws_profile_manager.cli <command>")
    
    run_app(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
