"""
Logging configuration for AWS Profile Manager
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "aws_profile_manager.log",
    enable_file_logging: bool = True,
    enable_console_logging: bool = True
) -> logging.Logger:
    """Setup application logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    # Create colorful formatter for console
    class ColoredFormatter(logging.Formatter):
        def __init__(self, fmt, datefmt=None):
            super().__init__(fmt, datefmt)
            # Color codes
            self.colors = {
                'DEBUG': '[36m',    # Cyan
                'INFO': '[32m',     # Green
                'WARNING': '[33m',  # Yellow
                'ERROR': '[31m',    # Red
                'CRITICAL': '[35m', # Magenta
                'RESET': '[0m'      # Reset
            }
        
        def format(self, record):
            # Add color to levelname
            if record.levelname in self.colors:
                record.levelname = f"{self.colors[record.levelname]}{record.levelname}{self.colors['RESET']}"
            return super().format(record)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Add file handler
    if enable_file_logging:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Add console handler
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging functionality"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        return logging.getLogger(self.__class__.__name__)
