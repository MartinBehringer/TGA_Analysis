"""
Main window UI layout for the TGA Analysis application.

This module contains only the UI layout definition (QMainWindow).
Signal/slot wiring and business logic are in controllers.py.
"""

from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QDockWidget, QListWidget, QListWidgetItem,
    QPushButton, QCheckBox, QRadioButton, QButtonGroup,
    QLabel, QSpinBox, QLineEdit, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTextEdit, QAbstractItemView, QSizePolicy, QFrame,
    QToolBox, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QMoveEvent

from app.scaling import scaled, scaled_f, scaled_font_pt, sf

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure


class OddSpinBox(QSpinBox):
    """SpinBox that only allows odd values."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimum(3)
        self.setMaximum(1001)
        self.setSingleStep(2)
        self.setValue(201)
    
    def stepBy(self, steps: int):
        new_value = self.value() + steps * 2
        if new_value % 2 == 0:
            new_value += 1
        self.setValue(new_value)
    
    def validate(self, text: str, pos: int):
        result = super().validate(text, pos)
        try:
            val = int(text)
            if val % 2 == 0:
                return (self.Intermediate, text, pos)
        except ValueError:
            pass
        return result
    
    def fixup(self, text: str):
        try:
            val = int(text)
            if val % 2 == 0:
                val += 1
            self.setValue(val)
        except ValueError:
            self.setValue(201)


class MainWindow(QMainWindow):
    """
    Main application window for TGA Analysis.
    
    Layout:
    - Central: Vertical QSplitter
      - Top: Overview matplotlib canvas + toolbar
      - Bottom: QTabWidget (Ranges & Results, Raw Data, Logs)
    - Right dock: Controls panel
    """
    
    # Signals for controller to connect
    files_open_requested = pyqtSignal()
    files_remove_requested = pyqtSignal()
    files_clear_requested = pyqtSignal()
    curve_selection_changed = pyqtSignal()
    calc_use_series_changed = pyqtSignal(str)
    marsh_params_changed = pyqtSignal(int, int, float)
    show_tg_changed = pyqtSignal(bool)
    show_dtg_changed = pyqtSignal(bool)
    x_axis_changed = pyqtSignal(str)
    normalize_changed = pyqtSignal(bool)
    dtg_smoothing_changed = pyqtSignal(bool, int, int)
    tg_smoothing_changed = pyqtSignal(bool, int, int)
    overlay_raw_changed = pyqtSignal(bool)
    slope_window_preview_changed = pyqtSignal(bool)
    range_add_requested = pyqtSignal()
    range_duplicate_requested = pyqtSignal()
    range_remove_requested = pyqtSignal()
    range_clear_requested = pyqtSignal()
    range_selected = pyqtSignal(int)
    calculate_requested = pyqtSignal()
    export_results_requested = pyqtSignal(str)  # 'tsv' or 'json'
    result_selected = pyqtSignal(int)
    save_config_requested = pyqtSignal()
    load_config_requested = pyqtSignal()
    include_derived_changed = pyqtSignal(bool)
    filter_text_changed = pyqtSignal(str)
    screen_changed = pyqtSignal()  # emitted when window moves to a different screen
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TGA Analysis Tool")
        self.setMinimumSize(scaled(1100), scaled(700))
        self.resize(scaled(1500), scaled(950))
        self._detail_full_range = None
        self._detail_context = None
        self._current_screen_name: str = ""
        
        self._setup_ui()
        self._connect_internal_signals()
    
    # ------------------------------------------------------------------
    # Multi-monitor: detect when the window moves to a different screen
    # ------------------------------------------------------------------

    def moveEvent(self, event: QMoveEvent):
        """Detect screen changes when the window is dragged between monitors."""
        super().moveEvent(event)
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return
            desktop = app.desktop()
            screen_num = desktop.screenNumber(self)
            screen_rect = desktop.availableGeometry(screen_num)
            screen_key = f"{screen_rect.width()}x{screen_rect.height()}"
            if self._current_screen_name and screen_key != self._current_screen_name:
                # Screen changed – recompute scale and notify controller
                from app.scaling import _recompute_for_screen
                _recompute_for_screen(screen_rect)
                self._apply_rescaled_stylesheet()
                self.screen_changed.emit()
            self._current_screen_name = screen_key
        except Exception:
            pass  # never crash on move

    def _apply_rescaled_stylesheet(self):
        """Re-apply the global stylesheet with new scale factor."""
        from PyQt5.QtWidgets import QApplication
        from app.styles import MODERN_STYLESHEET
        from app.scaling import scale_stylesheet, scaled_font_pt
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(scale_stylesheet(MODERN_STYLESHEET))
            app.setFont(QFont('Segoe UI', scaled_font_pt(10)))
    
    def _setup_ui(self):
        """Set up the complete UI layout."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(scaled(5), scaled(5), scaled(5), scaled(5))
        
        self.main_splitter = QSplitter(Qt.Vertical)
        central_layout.addWidget(self.main_splitter)
        
        # Top: Overview plot
        self._setup_overview_panel()
        
        # Bottom: Tab widget
        self._setup_tab_widget()
        
        # Set splitter sizes (slightly more space for plot)
        self.main_splitter.setSizes([scaled(520), scaled(580)])
        
        # Right dock: Controls
        self._setup_controls_dock()
    
    def _setup_overview_panel(self):
        """Set up the overview plot panel."""
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        
        # Matplotlib figure and canvas
        self.overview_figure = Figure(figsize=(scaled_f(8), scaled_f(5)), dpi=100)
        self.overview_canvas = FigureCanvas(self.overview_figure)
        self.overview_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Navigation toolbar
        self.overview_toolbar = NavigationToolbar(self.overview_canvas, overview_widget)
        
        overview_layout.addWidget(self.overview_toolbar)
        overview_layout.addWidget(self.overview_canvas)
        
        self.main_splitter.addWidget(overview_widget)
    
    def _setup_tab_widget(self):
        """Set up the bottom tab widget."""
        self.tab_widget = QTabWidget()
        
        # Tab 1: Ranges
        self._setup_ranges_tab()

        # Tab 2: Results
        self._setup_results_tab()

        # Tab 3: Detail Plot
        self._setup_detail_tab()

        # Tab 4: Raw Data
        self._setup_raw_data_tab()

        # Tab 5: Measurement Info
        self._setup_measurement_info_tab()
        
        self.main_splitter.addWidget(self.tab_widget)
    
    def _setup_ranges_tab(self):
        """Set up the Ranges & Results tab."""
        ranges_widget = QWidget()
        ranges_layout = QVBoxLayout(ranges_widget)
        
        # Splitter for tables
        tables_splitter = QSplitter(Qt.Vertical)
        
        # Ranges table group
        ranges_group = QGroupBox("Calculation Ranges")
        ranges_group_layout = QVBoxLayout(ranges_group)
        
        self.ranges_table = QTableWidget()
        self.ranges_table.setColumnCount(5)
        self.ranges_table.setHorizontalHeaderLabels([
            "Start Temp (°C)", "End Temp (°C)", "Method", "Curve", "ΔY (%)"
        ])
        self.ranges_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ranges_table.verticalHeader().setDefaultSectionSize(scaled(36))
        self.ranges_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ranges_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ranges_table.setStyleSheet(
            f"QTableWidget::item{{padding:{scaled(8)}px;}}"
            f"QTableWidget QLineEdit{{padding:{scaled(4)}px {scaled(8)}px; border:1px solid #d1d1d6; border-radius:{scaled(4)}px; min-height:{scaled(22)}px;}}"
        )
        self.ranges_table.itemChanged.connect(self._on_ranges_item_changed)
        ranges_group_layout.addWidget(self.ranges_table)
        
        # Ranges buttons
        ranges_btn_layout = QHBoxLayout()
        self.btn_add_range = QPushButton("Add")
        self.btn_duplicate_range = QPushButton("Duplicate")
        self.btn_remove_range = QPushButton("Remove")
        self.btn_clear_ranges = QPushButton("Clear")
        self.btn_calculate = QPushButton("Calculate")
        self.btn_calculate.setStyleSheet("font-weight: bold;")
        
        ranges_btn_layout.addWidget(self.btn_add_range)
        ranges_btn_layout.addWidget(self.btn_duplicate_range)
        ranges_btn_layout.addWidget(self.btn_remove_range)
        ranges_btn_layout.addWidget(self.btn_clear_ranges)
        ranges_btn_layout.addStretch()
        ranges_btn_layout.addWidget(self.btn_calculate)
        ranges_group_layout.addLayout(ranges_btn_layout)
        
        tables_splitter.addWidget(ranges_group)

        # Set splitter sizes
        tables_splitter.setSizes([scaled(400)])
        
        ranges_layout.addWidget(tables_splitter)
        
        self.tab_widget.addTab(ranges_widget, "Ranges")
    
    def _setup_detail_tab(self):
        """Set up the Detail Plot tab."""
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(scaled(5), scaled(5), scaled(5), scaled(5))
        
        self.detail_figure = Figure(figsize=(scaled_f(8), scaled_f(5)), dpi=100)
        self.detail_canvas = FigureCanvas(self.detail_figure)
        self.detail_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detail_toolbar = NavigationToolbar(self.detail_canvas, detail_widget)
        
        detail_layout.addWidget(self.detail_toolbar)
        detail_layout.addWidget(self.detail_canvas)

        # Click to pop up larger view
        self.detail_canvas.mpl_connect(
            'button_press_event',
            lambda event: self._open_plot_popup(self.detail_figure, "Detail Plot")
        )
        
        self.tab_widget.addTab(detail_widget, "Detail Plot")

    def _setup_results_tab(self):
        """Set up the Results tab."""
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(12)
        self.results_table.setHorizontalHeaderLabels([
            "Timestamp", "Curve", "Method", "Start (°C)", "End (°C)",
            "Use Series", "ΔY (%)", "Slope Window Lower", "Slope Window Upper",
            "Turning Temp (°C)", "Details"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        results_layout.addWidget(self.results_table)

        # Results export buttons
        results_btn_layout = QHBoxLayout()
        self.btn_export_tsv = QPushButton("Export TSV")
        self.btn_export_json = QPushButton("Export JSON")
        self.btn_clear_results = QPushButton("Clear Results")

        results_btn_layout.addWidget(self.btn_export_tsv)
        results_btn_layout.addWidget(self.btn_export_json)
        results_btn_layout.addStretch()
        results_btn_layout.addWidget(self.btn_clear_results)
        results_layout.addLayout(results_btn_layout)

        self.tab_widget.addTab(results_widget, "Results")
    
    def _setup_raw_data_tab(self):
        """Set up the Raw Data tab."""
        raw_data_widget = QWidget()
        raw_data_layout = QVBoxLayout(raw_data_widget)
        
        # Options
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Viewing:"))
        self.raw_data_curve_combo = QComboBox()
        self.raw_data_curve_combo.setMinimumWidth(scaled(200))
        options_layout.addWidget(self.raw_data_curve_combo)
        
        self.include_derived_checkbox = QCheckBox("Include derived columns (dtg_raw, dtg_smooth, tg_smooth)")
        options_layout.addWidget(self.include_derived_checkbox)
        options_layout.addStretch()
        raw_data_layout.addLayout(options_layout)
        
        # Data table
        self.raw_data_table = QTableWidget()
        self.raw_data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.raw_data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        raw_data_layout.addWidget(self.raw_data_table)
        
        self.tab_widget.addTab(raw_data_widget, "Raw Data")

    def _setup_measurement_info_tab(self):
        """Set up the Measurement Info tab."""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Curve:"))
        self.measurement_curve_combo = QComboBox()
        self.measurement_curve_combo.setMinimumWidth(scaled(220))
        top_layout.addWidget(self.measurement_curve_combo)
        top_layout.addStretch()
        info_layout.addLayout(top_layout)

        self.measurement_info_text = QTextEdit()
        self.measurement_info_text.setReadOnly(True)
        self.measurement_info_text.setFont(QFont("Consolas", scaled_font_pt(9)))
        info_layout.addWidget(self.measurement_info_text)

        self.tab_widget.addTab(info_widget, "Measurement Info")
    
    def _setup_controls_dock(self):
        """Set up the controls dock widget."""
        self.controls_dock = QDockWidget("Controls", self)
        self.controls_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.controls_dock.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setSpacing(scaled(10))
        
        # File controls
        file_group = QGroupBox("Files")
        file_layout = QVBoxLayout(file_group)
        
        file_btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open")
        self.btn_remove = QPushButton("Remove")
        self.btn_clear = QPushButton("Clear All")
        file_btn_layout.addWidget(self.btn_open)
        file_btn_layout.addWidget(self.btn_remove)
        file_btn_layout.addWidget(self.btn_clear)
        file_layout.addLayout(file_btn_layout)
        
        # Filter box
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search curves...")
        filter_layout.addWidget(self.filter_edit)
        file_layout.addLayout(filter_layout)
        
        # Curve list
        self.curve_list = QListWidget()
        self.curve_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.curve_list.setMinimumHeight(scaled(150))
        file_layout.addWidget(self.curve_list)
        
        controls_layout.addWidget(file_group)

        # Accordion for Display and Smoothing
        accordion = QToolBox()
        accordion.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Display section
        display_page = QWidget()
        display_layout = QVBoxLayout(display_page)

        self.show_tg_checkbox = QCheckBox("Show TG")
        self.show_tg_checkbox.setChecked(True)
        self.show_dtg_checkbox = QCheckBox("Show DTG")
        self.show_dtg_checkbox.setChecked(True)

        display_layout.addWidget(self.show_tg_checkbox)
        display_layout.addWidget(self.show_dtg_checkbox)

        # X-axis mode
        xaxis_layout = QHBoxLayout()
        xaxis_layout.addWidget(QLabel("X-axis:"))
        self.xaxis_temp_radio = QRadioButton("Temperature")
        self.xaxis_temp_radio.setChecked(True)
        self.xaxis_time_radio = QRadioButton("Time")
        self.xaxis_group = QButtonGroup()
        self.xaxis_group.addButton(self.xaxis_temp_radio)
        self.xaxis_group.addButton(self.xaxis_time_radio)
        xaxis_layout.addWidget(self.xaxis_temp_radio)
        xaxis_layout.addWidget(self.xaxis_time_radio)
        display_layout.addLayout(xaxis_layout)

        # Normalization
        self.normalize_checkbox = QCheckBox("Normalize to 100% at 40°C")
        self.normalize_checkbox.setToolTip(
            "Displayed TG values are scaled so that Mass(40°C) = 100%.\n"
            "Raw data is unchanged. Calculations can still use Raw TG."
        )
        display_layout.addWidget(self.normalize_checkbox)
        display_layout.addStretch()

        accordion.addItem(display_page, "Display")

        # DTG Smoothing section
        dtg_page = QWidget()
        dtg_layout = QFormLayout(dtg_page)

        self.dtg_smooth_checkbox = QCheckBox("Enable")
        self.dtg_smooth_checkbox.setChecked(True)
        dtg_layout.addRow(self.dtg_smooth_checkbox)

        self.dtg_window_spin = OddSpinBox()
        self.dtg_window_spin.setValue(201)
        dtg_layout.addRow("Window:", self.dtg_window_spin)

        self.dtg_poly_spin = QSpinBox()
        self.dtg_poly_spin.setMinimum(1)
        self.dtg_poly_spin.setMaximum(10)
        self.dtg_poly_spin.setValue(3)
        dtg_layout.addRow("Poly order:", self.dtg_poly_spin)

        accordion.addItem(dtg_page, "DTG Smoothing")

        # TG Smoothing section
        tg_page = QWidget()
        tg_layout = QFormLayout(tg_page)

        self.tg_smooth_checkbox = QCheckBox("Enable")
        self.tg_smooth_checkbox.setChecked(False)
        tg_layout.addRow(self.tg_smooth_checkbox)

        self.tg_window_spin = OddSpinBox()
        self.tg_window_spin.setValue(201)
        tg_layout.addRow("Window:", self.tg_window_spin)

        self.tg_poly_spin = QSpinBox()
        self.tg_poly_spin.setMinimum(1)
        self.tg_poly_spin.setMaximum(10)
        self.tg_poly_spin.setValue(3)
        tg_layout.addRow("Poly order:", self.tg_poly_spin)

        accordion.addItem(tg_page, "TG Smoothing")

        # Tangential-Marsh parameters
        marsh_page = QWidget()
        marsh_layout = QFormLayout(marsh_page)

        self.calc_window_pts_left_spin = QSpinBox()
        self.calc_window_pts_left_spin.setMinimum(5)
        self.calc_window_pts_left_spin.setMaximum(500)
        self.calc_window_pts_left_spin.setValue(30)
        marsh_layout.addRow("Slope window (lower):", self.calc_window_pts_left_spin)

        self.calc_window_pts_right_spin = QSpinBox()
        self.calc_window_pts_right_spin.setMinimum(5)
        self.calc_window_pts_right_spin.setMaximum(500)
        self.calc_window_pts_right_spin.setValue(30)
        marsh_layout.addRow("Slope window (upper):", self.calc_window_pts_right_spin)

        self.marsh_turning_frac_spin = QSpinBox()
        self.marsh_turning_frac_spin.setMinimum(0)
        self.marsh_turning_frac_spin.setMaximum(100)
        self.marsh_turning_frac_spin.setValue(50)
        marsh_layout.addRow("Turning temp (%):", self.marsh_turning_frac_spin)

        self.btn_show_slope_window = QPushButton("Show slope window")
        self.btn_show_slope_window.setCheckable(True)
        self.btn_show_slope_window.setToolTip(
            "Shade the slope-window regions on the overview plot for the selected range"
        )
        marsh_layout.addRow(self.btn_show_slope_window)

        accordion.addItem(marsh_page, "Tangential-Marsh")

        controls_layout.addWidget(accordion)

        # Global calculation series
        calc_series_layout = QHBoxLayout()
        calc_series_layout.addWidget(QLabel("Calc series:"))
        self.calc_series_combo = QComboBox()
        self.calc_series_combo.addItems(["Raw TG", "Smoothed TG"])
        self.calc_series_combo.setMinimumWidth(scaled(140))
        calc_series_layout.addWidget(self.calc_series_combo)
        controls_layout.addLayout(calc_series_layout)
        
        # Overlay raw
        self.overlay_raw_checkbox = QCheckBox("Overlay original (raw) series")
        self.overlay_raw_checkbox.setToolTip(
            "Show raw data behind smoothed curves with transparency"
        )
        controls_layout.addWidget(self.overlay_raw_checkbox)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        controls_layout.addWidget(separator)

        # Save/Load configuration buttons
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout(config_group)
        self.btn_save_config = QPushButton("Save")
        self.btn_save_config.setToolTip("Save current configuration (curves, ranges, settings)")
        self.btn_load_config = QPushButton("Load")
        self.btn_load_config.setToolTip("Load a saved configuration")
        config_layout.addWidget(self.btn_save_config)
        config_layout.addWidget(self.btn_load_config)
        controls_layout.addWidget(config_group)
        
        # Stretch at bottom
        controls_layout.addStretch()
        
        self.controls_dock.setWidget(controls_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.controls_dock)

    def _open_plot_popup(self, fig: Figure, title: str):
        """Open the given matplotlib figure in a pop-up dialog."""
        import pickle

        if title == "Detail Plot" and self._detail_context is not None:
            # Rebuild detail plot with full curve range
            from app.plotting import plot_detail
            curve, result, slope_overlay = self._detail_context
            fig_copy = Figure(figsize=fig.get_size_inches(), dpi=fig.dpi)
            plot_detail(fig_copy, curve, result, full_range=True,
                        slope_window_overlay=slope_overlay)
        else:
            try:
                fig_copy = pickle.loads(pickle.dumps(fig))
            except Exception:
                fig_copy = Figure(figsize=fig.get_size_inches(), dpi=fig.dpi)

            # Apply full range if available
            self._apply_full_range(fig_copy, title)

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(scaled(1100), scaled(750))

        layout = QVBoxLayout(dialog)
        canvas = FigureCanvas(fig_copy)
        toolbar = NavigationToolbar(canvas, dialog)

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dialog.setLayout(layout)
        dialog.exec_()

    def set_detail_full_range(self, x_vals, y_vals) -> None:
        """Store full-range data for detail plot pop-up."""
        try:
            self._detail_full_range = (
                float(min(x_vals)),
                float(max(x_vals)),
                float(min(y_vals)),
                float(max(y_vals))
            )
        except Exception:
            self._detail_full_range = None

    def set_detail_context(self, curve, result, slope_overlay=None) -> None:
        """Store curve/result context for detail plot popup."""
        self._detail_context = (curve, result, slope_overlay)

    def _apply_full_range(self, fig: Figure, title: str) -> None:
        """Apply full data range to axes in the popup figure."""
        if title == "Detail Plot" and self._detail_full_range:
            x_min, x_max, y_min, y_max = self._detail_full_range
            for ax in fig.get_axes():
                ax.set_xlim(x_min, x_max)
                ax.set_ylim(y_min, y_max)
            return

        # For overview or other plots, compute from line data
        for ax in fig.get_axes():
            x_vals = []
            y_vals = []
            for line in ax.get_lines():
                x_data = line.get_xdata()
                y_data = line.get_ydata()
                if x_data is not None and len(x_data) > 0:
                    x_vals.append(min(x_data))
                    x_vals.append(max(x_data))
                if y_data is not None and len(y_data) > 0:
                    y_vals.append(min(y_data))
                    y_vals.append(max(y_data))
            if x_vals and y_vals:
                ax.set_xlim(min(x_vals), max(x_vals))
                ax.set_ylim(min(y_vals), max(y_vals))
    
    def _connect_internal_signals(self):
        """Connect widget signals to main window signals."""
        # File controls
        self.btn_open.clicked.connect(self.files_open_requested.emit)
        self.btn_remove.clicked.connect(self.files_remove_requested.emit)
        self.btn_clear.clicked.connect(self.files_clear_requested.emit)
        
        # Curve list
        self.curve_list.itemSelectionChanged.connect(self.curve_selection_changed.emit)
        
        # Filter
        self.filter_edit.textChanged.connect(self.filter_text_changed.emit)
        
        # Display toggles
        self.show_tg_checkbox.toggled.connect(self.show_tg_changed.emit)
        self.show_dtg_checkbox.toggled.connect(self.show_dtg_changed.emit)
        
        # X-axis
        self.xaxis_temp_radio.toggled.connect(
            lambda checked: self.x_axis_changed.emit("Temperature") if checked else None
        )
        self.xaxis_time_radio.toggled.connect(
            lambda checked: self.x_axis_changed.emit("Time") if checked else None
        )
        
        # Normalization
        self.normalize_checkbox.toggled.connect(self.normalize_changed.emit)
        
        # DTG smoothing
        self.dtg_smooth_checkbox.toggled.connect(self._emit_dtg_smoothing)
        self.dtg_window_spin.valueChanged.connect(self._emit_dtg_smoothing)
        self.dtg_poly_spin.valueChanged.connect(self._emit_dtg_smoothing)
        
        # TG smoothing
        self.tg_smooth_checkbox.toggled.connect(self._emit_tg_smoothing)
        self.tg_window_spin.valueChanged.connect(self._emit_tg_smoothing)
        self.tg_poly_spin.valueChanged.connect(self._emit_tg_smoothing)
        
        # Overlay raw
        self.overlay_raw_checkbox.toggled.connect(self.overlay_raw_changed.emit)

        # Calc series
        self.calc_series_combo.currentTextChanged.connect(self.calc_use_series_changed.emit)

        # Tangential-Marsh params
        self.calc_window_pts_left_spin.valueChanged.connect(self._emit_marsh_params)
        self.calc_window_pts_right_spin.valueChanged.connect(self._emit_marsh_params)
        self.marsh_turning_frac_spin.valueChanged.connect(self._emit_marsh_params)
        self.btn_show_slope_window.toggled.connect(self.slope_window_preview_changed.emit)
        
        # Ranges
        self.btn_add_range.clicked.connect(self.range_add_requested.emit)
        self.btn_duplicate_range.clicked.connect(self.range_duplicate_requested.emit)
        self.btn_remove_range.clicked.connect(self.range_remove_requested.emit)
        self.btn_clear_ranges.clicked.connect(self.range_clear_requested.emit)
        self.btn_calculate.clicked.connect(self.calculate_requested.emit)
        self.ranges_table.itemSelectionChanged.connect(self._emit_range_selected)
        
        # Results
        self.btn_export_tsv.clicked.connect(lambda: self.export_results_requested.emit('tsv'))
        self.btn_export_json.clicked.connect(lambda: self.export_results_requested.emit('json'))
        self.btn_clear_results.clicked.connect(self._clear_results)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        
        # Save/Load config
        self.btn_save_config.clicked.connect(self.save_config_requested.emit)
        self.btn_load_config.clicked.connect(self.load_config_requested.emit)
        
        # Raw data
        self.include_derived_checkbox.toggled.connect(self.include_derived_changed.emit)
        self.raw_data_curve_combo.currentIndexChanged.connect(self._on_raw_data_curve_changed)

        # Measurement info
        self.measurement_curve_combo.currentIndexChanged.connect(self._on_measurement_curve_changed)
    
    def _emit_dtg_smoothing(self):
        """Emit DTG smoothing signal with current values."""
        self.dtg_smoothing_changed.emit(
            self.dtg_smooth_checkbox.isChecked(),
            self.dtg_window_spin.value(),
            self.dtg_poly_spin.value()
        )
    
    def _emit_tg_smoothing(self):
        """Emit TG smoothing signal with current values."""
        self.tg_smoothing_changed.emit(
            self.tg_smooth_checkbox.isChecked(),
            self.tg_window_spin.value(),
            self.tg_poly_spin.value()
        )

    def _emit_marsh_params(self):
        """Emit Tangential-Marsh parameter changes."""
        self.marsh_params_changed.emit(
            self.calc_window_pts_left_spin.value(),
            self.calc_window_pts_right_spin.value(),
            self.marsh_turning_frac_spin.value() / 100.0
        )
    
    def _on_result_selected(self):
        """Handle result row selection."""
        rows = self.results_table.selectionModel().selectedRows()
        if rows:
            self.result_selected.emit(rows[0].row())
    
    def _on_raw_data_curve_changed(self, index: int):
        """Handle raw data curve combo change."""
        # This will be connected to controller for actual data loading
        pass

    def _on_measurement_curve_changed(self, index: int):
        """Handle measurement info curve combo change."""
        self._update_measurement_info_text()

    def _on_ranges_item_changed(self, item: QTableWidgetItem):
        """Clear delta when range inputs change."""
        if item.column() in (0, 1):
            self._clear_range_delta(item.row())

    def _emit_range_selected(self):
        """Emit range_selected when selection changes."""
        row = self.get_selected_range_row()
        if row >= 0:
            self.range_selected.emit(row)
    
    def _clear_results(self):
        """Clear results table."""
        self.results_table.setRowCount(0)
    
    # Public methods for controller to update UI
    
    def update_curve_list(self, curves: list, selected_indices: list):
        """Update the curve list widget."""
        self._measurement_curves = curves
        self.curve_list.blockSignals(True)
        self.curve_list.clear()
        
        filter_text = self.filter_edit.text().lower()
        
        for i, curve in enumerate(curves):
            if filter_text and filter_text not in curve.name.lower():
                continue
            
            item = QListWidgetItem(curve.name)
            item.setData(Qt.UserRole, i)  # Store actual index
            item.setToolTip(curve.path)
            self.curve_list.addItem(item)
            
            if i in selected_indices:
                item.setSelected(True)
        
        self.curve_list.blockSignals(False)
        
        # Update ranges curve combos
        self._update_ranges_curve_combos(curves, selected_indices)
        
        # Update raw data combo
        self._update_raw_data_combo(curves)

        # Update measurement info combo
        self._update_measurement_combo(curves)
    
    def _update_raw_data_combo(self, curves: list):
        """Update the raw data curve combo box."""
        self.raw_data_curve_combo.blockSignals(True)
        current_text = self.raw_data_curve_combo.currentText()
        self.raw_data_curve_combo.clear()
        
        for i, curve in enumerate(curves):
            self.raw_data_curve_combo.addItem(curve.name, i)
        
        # Try to restore selection
        idx = self.raw_data_curve_combo.findText(current_text)
        if idx >= 0:
            self.raw_data_curve_combo.setCurrentIndex(idx)
        
        self.raw_data_curve_combo.blockSignals(False)

    def _update_measurement_combo(self, curves: list):
        """Update the measurement info curve combo box."""
        self.measurement_curve_combo.blockSignals(True)
        current_text = self.measurement_curve_combo.currentText()
        self.measurement_curve_combo.clear()

        for i, curve in enumerate(curves):
            self.measurement_curve_combo.addItem(curve.name, i)

        idx = self.measurement_curve_combo.findText(current_text)
        if idx >= 0:
            self.measurement_curve_combo.setCurrentIndex(idx)

        self.measurement_curve_combo.blockSignals(False)
        self._update_measurement_info_text()

    def _update_measurement_info_text(self):
        """Update measurement info display for selected curve."""
        idx = self.measurement_curve_combo.currentData()
        if idx is None:
            self.measurement_info_text.setPlainText("No curve selected.")
            return
        try:
            curve = self._measurement_curves[idx]
        except Exception:
            self.measurement_info_text.setPlainText("No curve selected.")
            return

        header_lines = curve.parse_metadata.header_lines or []
        if not header_lines:
            self.measurement_info_text.setPlainText("No header information available.")
            return
        self.measurement_info_text.setPlainText("\n".join(header_lines))

    def _update_ranges_curve_combos(self, curves: list, selected_indices: list):
        """Update curve options for all range rows (selected curves only)."""
        allowed_indices = selected_indices or []
        for row in range(self.ranges_table.rowCount()):
            combo = self.ranges_table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                current_data = combo.currentData()
                self._update_single_range_curve_combo(combo, curves, allowed_indices, current_data)

    def _update_single_range_curve_combo(self, combo: QComboBox, curves: list, allowed_indices: list, curve_index: Optional[int]):
        """Update a single curve combo with allowed curves and select index if provided."""
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Select curve", None)
        for i in allowed_indices:
            if i < len(curves):
                combo.addItem(curves[i].name, i)
        if curve_index is not None:
            idx = combo.findData(curve_index)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _clear_range_delta(self, row: int):
        """Clear the delta value for a range row."""
        if 0 <= row < self.ranges_table.rowCount():
            item = self.ranges_table.item(row, 4)
            if item is None:
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.ranges_table.setItem(row, 4, item)
            item.setText("")

    def set_range_delta(self, row: int, value: float):
        """Set the delta value for a range row."""
        if 0 <= row < self.ranges_table.rowCount():
            item = self.ranges_table.item(row, 4)
            if item is None:
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.ranges_table.setItem(row, 4, item)
            item.setText(f"{value:.3f}")

    def set_range_curve_selection(self, row: int, curve_index: Optional[int]) -> None:
        """Set the curve selection for a given range row."""
        if 0 <= row < self.ranges_table.rowCount():
            combo = self.ranges_table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                curves = getattr(self, "_measurement_curves", [])
                selected_indices = self.get_selected_curve_indices()
                self._update_single_range_curve_combo(combo, curves, selected_indices, curve_index)
    
    def get_selected_curve_indices(self) -> list:
        """Get list of selected curve indices."""
        indices = []
        for item in self.curve_list.selectedItems():
            idx = item.data(Qt.UserRole)
            if idx is not None:
                indices.append(idx)
        return indices
    
    def update_raw_data_table(self, df):
        """Update the raw data preview table."""
        self.raw_data_table.clear()
        
        if df is None or df.empty:
            self.raw_data_table.setRowCount(0)
            self.raw_data_table.setColumnCount(0)
            return
        
        self.raw_data_table.setRowCount(len(df))
        self.raw_data_table.setColumnCount(len(df.columns))
        self.raw_data_table.setHorizontalHeaderLabels(list(df.columns))
        
        for i in range(len(df)):
            for j, col in enumerate(df.columns):
                val = df.iloc[i][col]
                if isinstance(val, float):
                    text = f"{val:.4f}"
                else:
                    text = str(val)
                self.raw_data_table.setItem(i, j, QTableWidgetItem(text))
    
    def add_range_row(self, start_temp: float = 100.0, end_temp: float = 200.0,
                      method: str = "Stepwise", curve_index: Optional[int] = None):
        """Add a new row to the ranges table."""
        row = self.ranges_table.rowCount()
        self.ranges_table.insertRow(row)
        self.ranges_table.setRowHeight(row, scaled(36))
        
        # Start temp
        start_item = QTableWidgetItem(str(start_temp))
        self.ranges_table.setItem(row, 0, start_item)
        
        # End temp
        end_item = QTableWidgetItem(str(end_temp))
        self.ranges_table.setItem(row, 1, end_item)
        
        # Method combo
        method_combo = QComboBox()
        method_combo.addItems(["Stepwise", "Software", "Tangential-Marsh"])
        method_combo.setCurrentText(method)
        method_combo.setMinimumHeight(scaled(28))
        self.ranges_table.setCellWidget(row, 2, method_combo)

        # Curve combo
        curve_combo = QComboBox()
        curve_combo.setMinimumHeight(scaled(28))
        curve_combo.addItem("Select curve", None)
        self.ranges_table.setCellWidget(row, 3, curve_combo)

        # Populate curve options for the new row
        try:
            curves = getattr(self, "_measurement_curves", [])
            selected_indices = self.get_selected_curve_indices()
            self._update_single_range_curve_combo(curve_combo, curves, selected_indices, curve_index)
        except Exception:
            pass
        
        # Delta output (read-only)
        delta_item = QTableWidgetItem("")
        delta_item.setFlags(delta_item.flags() & ~Qt.ItemIsEditable)
        self.ranges_table.setItem(row, 4, delta_item)

        # Clear delta when user edits
        method_combo.currentIndexChanged.connect(lambda _: self._clear_range_delta(row))
        curve_combo.currentIndexChanged.connect(lambda _: self._clear_range_delta(row))
    
    def get_ranges_data(self) -> list:
        """Get all ranges from the table."""
        ranges = []
        for row in range(self.ranges_table.rowCount()):
            try:
                start_temp = float(self.ranges_table.item(row, 0).text())
                end_temp = float(self.ranges_table.item(row, 1).text())
                
                method_combo = self.ranges_table.cellWidget(row, 2)
                method = method_combo.currentText() if method_combo else "Stepwise"
                
                curve_combo = self.ranges_table.cellWidget(row, 3)
                curve_index = curve_combo.currentData() if curve_combo else None
                curve_name = curve_combo.currentText() if curve_combo else ""
                
                ranges.append({
                    'row': row,
                    'start_temp': start_temp,
                    'end_temp': end_temp,
                    'method': method,
                    'curve_index': curve_index,
                    'curve_name': curve_name
                })
            except (ValueError, AttributeError):
                continue
        
        return ranges
    
    def add_result_row(self, result: dict) -> int:
        """Add a result row to the results table."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        columns = [
            result.get('timestamp', ''),
            result.get('curve_name', ''),
            result.get('method', ''),
            str(result.get('start_temp', '')),
            str(result.get('end_temp', '')),
            result.get('use_series', ''),
            f"{result.get('delta_y', 0):.4f}",
            str(result.get('window_pts_left', '')),
            str(result.get('window_pts_right', '')),
            str(result.get('turning_temp', '')),
            result.get('details', '')
        ]
        
        for col, text in enumerate(columns):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, col, item)

        return row

    def select_result_row(self, row: int) -> None:
        """Select a result row and ensure it is visible."""
        if 0 <= row < self.results_table.rowCount():
            self.results_table.selectRow(row)
            self.results_table.scrollToItem(self.results_table.item(row, 0))
    
    def get_selected_range_row(self) -> int:
        """Get the currently selected range row index."""
        rows = self.ranges_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1
    
    def get_raw_data_curve_index(self) -> int:
        """Get the selected curve index for raw data display."""
        return self.raw_data_curve_combo.currentData() or 0
