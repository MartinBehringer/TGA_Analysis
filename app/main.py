"""
TGA Analysis Application - Entry Point

This is the main entry point for the TGA Analysis application.
Run with: python -m app.main
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.ui_main_window import MainWindow
from app.controllers import AppController
from app.logging_setup import setup_logging, get_logger
from app.styles import MODERN_STYLESHEET, apply_matplotlib_style


def main():
    """Main entry point for the TGA Analysis application."""
    # Set up logging first
    setup_logging()
    
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("TGA Analysis Tool")
    app.setOrganizationName("TGA Analysis")
    app.setApplicationVersion("1.0.0")
    
    # Set base style and apply modern stylesheet
    app.setStyle('Fusion')
    app.setStyleSheet(MODERN_STYLESHEET)
    
    # Set default font
    font = QFont('Segoe UI', 10)
    app.setFont(font)
    
    # Apply matplotlib theme
    apply_matplotlib_style()
    
    # Create main window
    window = MainWindow()
    
    # Create controller (connects signals/slots)
    controller = AppController(window)
    
    # Show window
    window.show()
    
    # Run event loop
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
