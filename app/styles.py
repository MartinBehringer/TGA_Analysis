"""
Modern stylesheet for the TGA Analysis application.

A clean, professional light theme with subtle shadows and modern design.
"""

MODERN_STYLESHEET = """
/* ============================================
   Global Settings
   ============================================ */

* {
    font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
    font-size: 10pt;
}

QMainWindow {
    background-color: #f5f5f7;
}

QWidget {
    background-color: #f5f5f7;
    color: #1d1d1f;
}

/* ============================================
   Menu Bar & Menus
   ============================================ */

QMenuBar {
    background-color: #ffffff;
    color: #1d1d1f;
    border-bottom: 1px solid #e5e5e7;
    padding: 2px;
}

QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #e5e5e7;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #e5e5e7;
}

QMenu::separator {
    height: 1px;
    background-color: #e5e5e7;
    margin: 4px 8px;
}

/* ============================================
   Tool Bar
   ============================================ */

QToolBar {
    background-color: #ffffff;
    border: none;
    border-bottom: 1px solid #e5e5e7;
    padding: 2px;
    spacing: 2px;
}

QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
    margin: 1px;
}

QToolButton:hover {
    background-color: #e5e5e7;
}

QToolButton:pressed {
    background-color: #d1d1d6;
}

/* ============================================
   Dock Widget
   ============================================ */

QDockWidget {
    color: #1d1d1f;
}

QDockWidget::title {
    background-color: #ffffff;
    padding: 8px;
    border-bottom: 1px solid #e5e5e7;
    font-weight: 600;
    font-size: 10pt;
}

QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 2px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #e5e5e7;
    border-radius: 4px;
}

/* ============================================
   Group Box
   ============================================ */

QGroupBox {
    font-weight: 600;
    font-size: 10pt;
    border: 1px solid #e5e5e7;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #0066cc;
}

/* ============================================
   Push Button
   ============================================ */

QPushButton {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    min-width: 60px;
}

QPushButton:hover {
    background-color: #f5f5f7;
    border-color: #0066cc;
}

QPushButton:pressed {
    background-color: #e5e5e7;
}

QPushButton:disabled {
    background-color: #f5f5f7;
    color: #86868b;
    border-color: #e5e5e7;
}

/* Primary action button */
QPushButton[primary="true"], QPushButton#btn_calculate {
    background-color: #0066cc;
    color: #ffffff;
    border: none;
    font-weight: 600;
}

QPushButton[primary="true"]:hover, QPushButton#btn_calculate:hover {
    background-color: #0077ed;
}

QPushButton[primary="true"]:pressed, QPushButton#btn_calculate:pressed {
    background-color: #004499;
}

/* Danger button */
QPushButton[danger="true"] {
    background-color: #ff3b30;
    color: #ffffff;
    border: none;
}

QPushButton[danger="true"]:hover {
    background-color: #ff6961;
}

/* ============================================
   Line Edit
   ============================================ */

QLineEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0066cc;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border-color: #0066cc;
}

QLineEdit:disabled {
    background-color: #f5f5f7;
    color: #86868b;
}

QLineEdit::placeholder {
    color: #86868b;
}

/* ============================================
   Spin Box
   ============================================ */

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 4px 8px;
    min-width: 70px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #0066cc;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #e5e5e7;
    border-top-right-radius: 5px;
    background-color: #f5f5f7;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: #e5e5e7;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #e5e5e7;
    border-bottom-right-radius: 5px;
    background-color: #f5f5f7;
}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #e5e5e7;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 8px;
    height: 8px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 8px;
    height: 8px;
}

/* ============================================
   Combo Box
   ============================================ */

QComboBox {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 6px 10px;
    min-width: 100px;
}

QComboBox:focus {
    border-color: #0066cc;
}

QComboBox:hover {
    border-color: #86868b;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid #e5e5e7;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}

QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 2px;
    selection-background-color: #e5e5e7;
    selection-color: #1d1d1f;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 4px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #f5f5f7;
}

/* ============================================
   Check Box
   ============================================ */

QCheckBox {
    spacing: 8px;
    color: #1d1d1f;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #d1d1d6;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #0066cc;
}

QCheckBox::indicator:checked {
    background-color: #0066cc;
    border-color: #0066cc;
}

QCheckBox::indicator:checked:hover {
    background-color: #0077ed;
    border-color: #0077ed;
}

QCheckBox::indicator:disabled {
    background-color: #f5f5f7;
    border-color: #e5e5e7;
}

/* ============================================
   Radio Button
   ============================================ */

QRadioButton {
    spacing: 8px;
    color: #1d1d1f;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 10px;
    border: 1px solid #d1d1d6;
    background-color: #ffffff;
}

QRadioButton::indicator:hover {
    border-color: #0066cc;
}

QRadioButton::indicator:checked {
    background-color: #0066cc;
    border-color: #0066cc;
}

QRadioButton::indicator:checked:hover {
    background-color: #0077ed;
    border-color: #0077ed;
}

/* ============================================
   Tab Widget
   ============================================ */

QTabWidget::pane {
    border: 1px solid #e5e5e7;
    border-radius: 6px;
    background-color: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background-color: #f5f5f7;
    color: #86868b;
    border: 1px solid #e5e5e7;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:hover {
    background-color: #e5e5e7;
    color: #1d1d1f;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0066cc;
    border-bottom: 2px solid #0066cc;
}

/* ============================================
   List Widget
   ============================================ */

QListWidget {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #e5e5e7;
    border-radius: 6px;
    padding: 2px;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-radius: 4px;
    margin: 1px;
}

QListWidget::item:hover {
    background-color: #f5f5f7;
}

QListWidget::item:selected {
    background-color: #e5e5e7;
    color: #1d1d1f;
}

QListWidget::item:selected:hover {
    background-color: #d1d1d6;
}

/* ============================================
   Table Widget
   ============================================ */

QTableWidget, QTableView {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #e5e5e7;
    border-radius: 6px;
    gridline-color: #f5f5f7;
    selection-background-color: #e5e5e7;
    selection-color: #1d1d1f;
    outline: none;
}

QTableWidget::item, QTableView::item {
    padding: 6px;
    border: none;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #e5e5e7;
}

QTableWidget::item:hover, QTableView::item:hover {
    background-color: #f5f5f7;
}

QHeaderView::section {
    background-color: #f5f5f7;
    color: #0066cc;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #e5e5e7;
    border-right: 1px solid #f5f5f7;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: #e5e5e7;
}

QHeaderView::section:first {
    border-top-left-radius: 5px;
}

QHeaderView::section:last {
    border-top-right-radius: 5px;
    border-right: none;
}

QTableCornerButton::section {
    background-color: #f5f5f7;
    border: none;
    border-bottom: 1px solid #e5e5e7;
}

/* ============================================
   Text Edit
   ============================================ */

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #e5e5e7;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #0066cc;
    selection-color: #ffffff;
}

QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #0066cc;
}

/* ============================================
   Scroll Bar
   ============================================ */

QScrollBar:vertical {
    background-color: #f5f5f7;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #d1d1d6;
    min-height: 24px;
    border-radius: 5px;
    margin: 1px;
}

QScrollBar::handle:vertical:hover {
    background-color: #86868b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background-color: #f5f5f7;
    height: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #d1d1d6;
    min-width: 24px;
    border-radius: 5px;
    margin: 1px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #86868b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* ============================================
   Splitter
   ============================================ */

QSplitter::handle {
    background-color: #e5e5e7;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #0066cc;
}

/* ============================================
   Tool Tip
   ============================================ */

QToolTip {
    background-color: #1d1d1f;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 9pt;
}

/* ============================================
   Status Bar
   ============================================ */

QStatusBar {
    background-color: #ffffff;
    color: #86868b;
    border-top: 1px solid #e5e5e7;
    padding: 2px;
}

QStatusBar::item {
    border: none;
}

/* ============================================
   Progress Bar
   ============================================ */

QProgressBar {
    background-color: #e5e5e7;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #0066cc;
    border-radius: 4px;
}

/* ============================================
   Label
   ============================================ */

QLabel {
    color: #1d1d1f;
    background-color: transparent;
}

QLabel[heading="true"] {
    font-size: 14pt;
    font-weight: bold;
    color: #0066cc;
}

/* ============================================
   Frame
   ============================================ */

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    background-color: #e5e5e7;
    max-height: 1px;
}

/* ============================================
   Message Box
   ============================================ */

QMessageBox {
    background-color: #f5f5f7;
}

QMessageBox QLabel {
    color: #1d1d1f;
}

QMessageBox QPushButton {
    min-width: 70px;
}

/* ============================================
   Dialog
   ============================================ */

QDialog {
    background-color: #f5f5f7;
}

QDialogButtonBox QPushButton {
    min-width: 70px;
}

/* ============================================
   File Dialog
   ============================================ */

QFileDialog {
    background-color: #f5f5f7;
}

/* ============================================
   Matplotlib Canvas
   ============================================ */

FigureCanvas {
    background-color: #ffffff;
    border-radius: 6px;
}
"""


def get_matplotlib_style():
    """
    Return matplotlib rcParams for a matching light theme.

    Font-size values are scaled via the global UI scale factor so that
    plot text matches the rest of the application on any screen size.
    """
    from app.scaling import scaled_font_pt

    return {
        # Figure
        'figure.facecolor': '#ffffff',
        'figure.edgecolor': '#ffffff',
        'figure.titlesize': scaled_font_pt(12),
        'figure.titleweight': 'bold',
        
        # Axes
        'axes.facecolor': '#ffffff',
        'axes.edgecolor': '#d1d1d6',
        'axes.labelcolor': '#1d1d1f',
        'axes.titlecolor': '#1d1d1f',
        'axes.titlesize': scaled_font_pt(11),
        'axes.labelsize': scaled_font_pt(10),
        'axes.linewidth': 1,
        'axes.grid': True,
        'axes.axisbelow': True,
        'axes.prop_cycle': "cycler('color', ['#0066cc', '#ff3b30', '#34c759', '#ff9500', '#af52de', '#00c7be', '#ff6482', '#5856d6'])",
        
        # Grid
        'grid.color': '#e5e5e7',
        'grid.linestyle': '-',
        'grid.linewidth': 0.5,
        'grid.alpha': 0.7,
        
        # Ticks
        'xtick.color': '#86868b',
        'ytick.color': '#86868b',
        'xtick.labelsize': scaled_font_pt(9),
        'ytick.labelsize': scaled_font_pt(9),
        
        # Legend
        'legend.facecolor': '#ffffff',
        'legend.edgecolor': '#e5e5e7',
        'legend.labelcolor': '#1d1d1f',
        'legend.fontsize': scaled_font_pt(9),
        'legend.framealpha': 0.95,
        
        # Text
        'text.color': '#1d1d1f',
        
        # Lines
        'lines.linewidth': 1.5,
        
        # Savefig
        'savefig.facecolor': '#ffffff',
        'savefig.edgecolor': '#ffffff',
    }


def apply_matplotlib_style():
    """
    Apply the light theme to matplotlib.
    """
    import matplotlib.pyplot as plt
    from cycler import cycler
    
    style = get_matplotlib_style()
    
    # Handle prop_cycle separately
    colors = ['#0066cc', '#ff3b30', '#34c759', '#ff9500', '#af52de', '#00c7be', '#ff6482', '#5856d6']
    
    for key, value in style.items():
        if key != 'axes.prop_cycle':
            plt.rcParams[key] = value
    
    plt.rcParams['axes.prop_cycle'] = cycler(color=colors)
