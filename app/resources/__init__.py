"""
Resource utilities for the TGA Analysis application.
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource, works for dev and for PyInstaller.
    
    Args:
        relative_path: Relative path to the resource from the resources folder.
        
    Returns:
        Absolute path to the resource.
    """
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)


def get_app_dir() -> str:
    """
    Get the application directory (where logs etc. should be stored).
    
    Returns:
        Path to the application directory.
    """
    if hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script - use project root
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
