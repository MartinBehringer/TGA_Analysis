"""
Logging setup for the TGA Analysis application.

Provides:
- RotatingFileHandler configuration
- Helper to read/tail log files
- Log directory management
"""

import logging
import os
import csv
from typing import List, Optional, Dict

from app.resources import get_app_dir


# Default log configuration
LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "calculations.csv"
LOG_HEADERS = [
    "timestamp",
    "curve_name",
    "curve_path",
    "method",
    "start_temp",
    "end_temp",
    "use_series",
    "delta_y",
    "slope_window_lower",
    "slope_window_upper",
    "turning_temp",
    "details",
]
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_log_dir() -> str:
    """
    Get the log directory path, creating it if necessary.
    
    Returns:
        Absolute path to the log directory.
    """
    log_dir = os.path.join(get_app_dir(), LOG_DIR_NAME)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_log_file_path() -> str:
    """
    Get the main log file path.
    
    Returns:
        Absolute path to the main log file.
    """
    return os.path.join(get_log_dir(), LOG_FILE_NAME)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure the application logging with rotating file handler.
    
    Args:
        level: Logging level (default: INFO)
        
    Returns:
        The root logger configured for the application.
    """
    # Create log directory if needed and reset CSV log
    log_file = get_log_file_path()
    reset_log_file()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # Create console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(console_handler)
    
    # Create application-specific logger
    app_logger = logging.getLogger('tga_app')
    app_logger.setLevel(level)
    
    app_logger.info("Logging initialized. CSV log file: %s", log_file)
    
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Logger instance.
    """
    return logging.getLogger(f'tga_app.{name}')


def reset_log_file() -> None:
    """Clear and initialize the CSV calculation log file."""
    log_file = get_log_file_path()
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        writer.writeheader()


def append_calculation_log(row: Dict[str, str]) -> None:
    """Append a calculation row to the CSV log file."""
    log_file = get_log_file_path()
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        writer.writerow({k: row.get(k, "") for k in LOG_HEADERS})


def read_log_tail(num_lines: int = 2000) -> str:
    """
    Read the last N lines from the log file.
    
    Args:
        num_lines: Number of lines to read from the end.
        
    Returns:
        String containing the last N lines of the log.
    """
    log_file = get_log_file_path()
    
    if not os.path.exists(log_file):
        return "Log file not found."
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            tail_lines = lines[-num_lines:] if len(lines) > num_lines else lines
            return ''.join(tail_lines)
    except Exception as e:
        return f"Error reading log file: {e}"


def get_all_log_files() -> List[str]:
    """Get paths to all log files (CSV only)."""
    log_files = []
    main_log = get_log_file_path()
    if os.path.exists(main_log):
        log_files.append(main_log)
    return log_files


def open_log_folder() -> Optional[str]:
    """
    Open the log folder in the system file explorer.
    
    Returns:
        Path that was opened, or None if failed.
    """
    import subprocess
    import sys
    
    log_dir = get_log_dir()
    
    try:
        if sys.platform == 'win32':
            os.startfile(log_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', log_dir], check=True)
        else:
            subprocess.run(['xdg-open', log_dir], check=True)
        return log_dir
    except Exception:
        return None
