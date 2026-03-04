"""
Controller for the TGA Analysis application.

Handles signal/slot wiring between UI and data models.
No heavy math here - that's in processing.py.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject

from app.models import (
    AppState, CurveData, CalcRange, CalcResult, CalcMethod, 
    UseSeries, XAxisMode, SmoothingParams
)
from app.ui_main_window import MainWindow
from app.io_parsers import load_tga_file
from app.processing import (
    compute_dtg, smooth_series, normalize_mass_at_40,
    calculate_mass_loss, WINDOW_PTS, _find_nearest_index
)
from app.plotting import plot_overview, plot_detail, get_disambiguated_names
from app.logging_setup import get_logger, append_calculation_log

logger = get_logger('controllers')


class AppController(QObject):
    """
    Main application controller.
    
    Manages:
    - Application state
    - Signal/slot connections
    - Coordination between UI, I/O, and processing
    """
    
    def __init__(self, window: MainWindow):
        super().__init__()
        self.window = window
        self.state = AppState()
        
        # Derived data cache
        self._cache: Dict[str, Any] = {}
        self._range_result_index: Dict[int, int] = {}
        
        self._connect_signals()
        self._add_default_ranges()
        self._refresh_ui()
        
        logger.info("Application controller initialized")
    
    def _add_default_ranges(self):
        """Add default calculation ranges (450-550 and 600-800)."""
        self.window.add_range_row(450.0, 550.0, "Stepwise", None)
        self.window.add_range_row(600.0, 800.0, "Stepwise", None)
    
    def _connect_signals(self):
        """Connect all UI signals to handler methods."""
        w = self.window
        
        # File operations
        w.files_open_requested.connect(self._on_open_files)
        w.files_remove_requested.connect(self._on_remove_files)
        w.files_clear_requested.connect(self._on_clear_files)
        
        # Curve selection
        w.curve_selection_changed.connect(self._on_curve_selection_changed)
        w.filter_text_changed.connect(self._on_filter_changed)
        
        # Display settings
        w.show_tg_changed.connect(self._on_show_tg_changed)
        w.show_dtg_changed.connect(self._on_show_dtg_changed)
        w.x_axis_changed.connect(self._on_x_axis_changed)
        w.normalize_changed.connect(self._on_normalize_changed)
        
        # Smoothing
        w.dtg_smoothing_changed.connect(self._on_dtg_smoothing_changed)
        w.tg_smoothing_changed.connect(self._on_tg_smoothing_changed)
        w.overlay_raw_changed.connect(self._on_overlay_raw_changed)
        w.slope_window_preview_changed.connect(self._on_slope_window_preview_changed)

        # Calculation series
        w.calc_use_series_changed.connect(self._on_calc_use_series_changed)
        w.marsh_params_changed.connect(self._on_marsh_params_changed)
        
        # Ranges and calculations
        w.range_add_requested.connect(self._on_add_range)
        w.range_duplicate_requested.connect(self._on_duplicate_range)
        w.range_remove_requested.connect(self._on_remove_range)
        w.range_clear_requested.connect(self._on_clear_ranges)
        w.calculate_requested.connect(self._on_calculate)
        w.result_selected.connect(self._on_result_selected)
        w.range_selected.connect(self._on_range_selected)
        
        # Export
        w.export_results_requested.connect(self._on_export_results)

        # Save/Load config
        w.save_config_requested.connect(self._on_save_config)
        w.load_config_requested.connect(self._on_load_config)
        
        # Raw data
        w.include_derived_changed.connect(self._on_include_derived_changed)
        w.raw_data_curve_combo.currentIndexChanged.connect(self._on_raw_data_curve_changed)

        # Multi-monitor rescale
        w.screen_changed.connect(self._on_screen_changed)
    
    def _refresh_ui(self):
        """Refresh all UI elements based on current state."""
        self.window.update_curve_list(
            self.state.curves,
            self.state.selected_curve_indices
        )
        self._update_plot()
        self._update_raw_data_preview()
    
    def _invalidate_cache(self):
        """Invalidate all cached derived data."""
        self._cache.clear()
    
    # =========================================================================
    # File Operations
    # =========================================================================
    
    def _on_open_files(self):
        """Handle open files request."""
        filepaths, _ = QFileDialog.getOpenFileNames(
            self.window,
            "Open TGA Files",
            "",
            "All Files (*);;CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if not filepaths:
            return
        
        for filepath in filepaths:
            logger.info("Loading file: %s", filepath)
            
            curve, warnings = load_tga_file(filepath, self.window)
            
            if curve is not None:
                idx = self.state.add_curve(curve)
                logger.info("Loaded curve '%s' with %d data points", 
                           curve.name, len(curve.raw_df))
                
                if warnings:
                    for warn in warnings:
                        logger.warning("Parse warning: %s", warn)
                
                # Select newly added curve
                if idx not in self.state.selected_curve_indices:
                    self.state.selected_curve_indices.append(idx)
            else:
                logger.error("Failed to load: %s", filepath)
                QMessageBox.warning(
                    self.window,
                    "Load Failed",
                    f"Could not load file:\n{filepath}\n\nWarnings:\n" + "\n".join(warnings)
                )
        
        self._invalidate_cache()
        self._refresh_ui()
    
    def _on_remove_files(self):
        """Handle remove selected files request."""
        indices = sorted(self.window.get_selected_curve_indices(), reverse=True)
        
        for idx in indices:
            if idx < len(self.state.curves):
                logger.info("Removing curve: %s", self.state.curves[idx].name)
                self.state.remove_curve(idx)
        
        self._invalidate_cache()
        self._refresh_ui()
    
    def _on_clear_files(self):
        """Handle clear all files request."""
        if not self.state.curves:
            return
        
        reply = QMessageBox.question(
            self.window,
            "Clear All",
            "Remove all loaded curves?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("Clearing all curves")
            self.state.clear_curves()
            self._invalidate_cache()
            self._refresh_ui()
    
    # =========================================================================
    # Curve Selection
    # =========================================================================
    
    def _on_curve_selection_changed(self):
        """Handle curve selection change in list."""
        self.state.selected_curve_indices = self.window.get_selected_curve_indices()
        logger.debug("Selection changed: %s", self.state.selected_curve_indices)
        self._update_plot()
        self._update_raw_data_preview()
        
        self.window.update_curve_list(
            self.state.curves,
            self.state.selected_curve_indices
        )
    
    def _on_filter_changed(self, text: str):
        """Handle filter text change."""
        self.window.update_curve_list(
            self.state.curves,
            self.state.selected_curve_indices
        )
    
    # =========================================================================
    # Display Settings
    # =========================================================================
    
    def _on_show_tg_changed(self, checked: bool):
        """Handle show TG toggle."""
        self.state.show_tg = checked
        logger.debug("Show TG: %s", checked)
        self._update_plot()
    
    def _on_show_dtg_changed(self, checked: bool):
        """Handle show DTG toggle."""
        self.state.show_dtg = checked
        logger.debug("Show DTG: %s", checked)
        self._update_plot()
    
    def _on_x_axis_changed(self, mode: str):
        """Handle X-axis mode change."""
        self.state.x_axis_mode = XAxisMode.TEMPERATURE if mode == "Temperature" else XAxisMode.TIME
        logger.debug("X-axis mode: %s", mode)
        self._invalidate_cache()
        self._update_plot()
    
    def _on_normalize_changed(self, checked: bool):
        """Handle normalization toggle."""
        self.state.normalize_at_40 = checked
        logger.debug("Normalize at 40°C: %s", checked)
        self._invalidate_cache()
        self._update_plot()
    
    # =========================================================================
    # Smoothing Settings
    # =========================================================================
    
    def _on_dtg_smoothing_changed(self, enabled: bool, window: int, poly: int):
        """Handle DTG smoothing parameter change."""
        self.state.dtg_smoothing = SmoothingParams(enabled=enabled, window=window, poly=poly)
        logger.debug("DTG smoothing: enabled=%s, window=%d, poly=%d", enabled, window, poly)
        self._invalidate_cache()
        self._update_plot()
    
    def _on_tg_smoothing_changed(self, enabled: bool, window: int, poly: int):
        """Handle TG smoothing parameter change."""
        self.state.tg_smoothing = SmoothingParams(enabled=enabled, window=window, poly=poly)
        logger.debug("TG smoothing: enabled=%s, window=%d, poly=%d", enabled, window, poly)
        self._invalidate_cache()
        self._update_plot()
    
    def _on_overlay_raw_changed(self, checked: bool):
        """Handle overlay raw toggle."""
        self.state.overlay_raw = checked
        logger.debug("Overlay raw: %s", checked)
        self._update_plot()

    def _on_slope_window_preview_changed(self, checked: bool):
        """Handle slope-window preview toggle."""
        self.state.show_slope_window_preview = checked
        logger.debug("Slope-window preview: %s", checked)
        self._update_plot()

    def _on_screen_changed(self):
        """Handle window moved to a different monitor – redraw plots with new scale."""
        from app.scaling import sf
        logger.info("Screen changed – new scale factor: %.2f", sf())
        self._update_plot()
        # Re-draw detail plot if one is active
        if self.state.calc_results:
            row = self.window.results_table.currentRow()
            if 0 <= row < len(self.state.calc_results):
                self._update_detail_plot(self.state.calc_results[row])

    def _on_calc_use_series_changed(self, series: str):
        """Handle global calculation series change."""
        self.state.calc_use_series = UseSeries.SMOOTHED_TG if series == "Smoothed TG" else UseSeries.RAW_TG
        logger.debug("Calc series: %s", self.state.calc_use_series.value)

    def _on_marsh_params_changed(self, window_pts_left: int, window_pts_right: int, turning_fraction: float):
        """Handle Tangential-Marsh parameter change."""
        self.state.calc_window_pts_left = window_pts_left
        self.state.calc_window_pts_right = window_pts_right
        self.state.marsh_turning_fraction = turning_fraction
        logger.debug("Marsh params: window_pts_left=%d, window_pts_right=%d, turning_fraction=%.2f", 
                    window_pts_left, window_pts_right, turning_fraction)
        if self.state.show_slope_window_preview:
            self._update_plot()

    def _build_slope_window_overlay(self) -> Optional[Dict[str, Any]]:
        """Build x-ranges for slope-window overlay on the overview plot."""
        if not self.state.show_slope_window_preview:
            return None

        ranges = self.window.get_ranges_data()
        if not ranges:
            return None

        selected_row = self.window.get_selected_range_row()
        range_candidates: List[Dict[str, Any]] = []

        # Priority: selected Tangential-Marsh row -> any Tangential-Marsh row -> selected row -> first valid row
        if selected_row >= 0:
            selected = next((r for r in ranges if r.get('row') == selected_row), None)
            if selected and selected.get('method') == 'Tangential-Marsh':
                range_candidates.append(selected)

        range_candidates.extend(
            r for r in ranges
            if r.get('method') == 'Tangential-Marsh' and r not in range_candidates
        )

        if selected_row >= 0:
            selected = next((r for r in ranges if r.get('row') == selected_row), None)
            if selected and selected not in range_candidates:
                range_candidates.append(selected)

        range_candidates.extend(r for r in ranges if r not in range_candidates)

        selected_range = None
        for r in range_candidates:
            curve_index = r.get('curve_index')
            if isinstance(curve_index, int) and 0 <= curve_index < len(self.state.curves):
                selected_range = r
                break

        if selected_range is None:
            return None

        curve = self.state.curves[selected_range['curve_index']]
        temp = curve.raw_df['Temp_C'].values
        x_vals = curve.raw_df['Temp_C'].values if self.state.x_axis_mode == XAxisMode.TEMPERATURE else curve.raw_df['Time_min'].values

        if len(temp) == 0 or len(x_vals) != len(temp):
            return None

        idx_start = _find_nearest_index(temp, selected_range['start_temp'])
        idx_end = _find_nearest_index(temp, selected_range['end_temp'])

        if idx_start > idx_end:
            idx_start, idx_end = idx_end, idx_start

        def _window_bounds(center_idx: int, window_pts: int) -> Tuple[float, float]:
            lo_idx = max(0, center_idx - window_pts)
            hi_idx = min(len(x_vals) - 1, center_idx + window_pts)
            x_lo = float(x_vals[lo_idx])
            x_hi = float(x_vals[hi_idx])
            return (min(x_lo, x_hi), max(x_lo, x_hi))

        left_min, left_max = _window_bounds(idx_start, self.state.calc_window_pts_left)
        right_min, right_max = _window_bounds(idx_end, self.state.calc_window_pts_right)

        return {
            'left': (left_min, left_max),
            'right': (right_min, right_max),
        }

    def _build_detail_slope_window_overlay(
        self, curve, result: CalcResult
    ) -> Optional[Dict[str, Any]]:
        """Build slope-window overlay for the detail plot (always in temperature space)."""
        if not self.state.show_slope_window_preview:
            return None

        temp = curve.raw_df['Temp_C'].values
        if len(temp) == 0:
            return None

        idx_start = result.params.get(
            'idx_start', _find_nearest_index(temp, result.start_temp)
        )
        idx_end = result.params.get(
            'idx_end', _find_nearest_index(temp, result.end_temp)
        )

        wl = result.params.get('window_pts_left', self.state.calc_window_pts_left)
        wr = result.params.get('window_pts_right', self.state.calc_window_pts_right)

        def _window_bounds(center_idx: int, window_pts: int) -> Tuple[float, float]:
            lo = max(0, center_idx - window_pts)
            hi = min(len(temp) - 1, center_idx + window_pts)
            return (min(float(temp[lo]), float(temp[hi])),
                    max(float(temp[lo]), float(temp[hi])))

        left_min, left_max = _window_bounds(idx_start, wl)
        right_min, right_max = _window_bounds(idx_end, wr)

        return {
            'left': (left_min, left_max),
            'right': (right_min, right_max),
        }
    
    # =========================================================================
    # Plotting
    # =========================================================================
    
    def _update_plot(self):
        """Update the overview plot."""
        selected_curves = self.state.get_selected_curves()
        display_names = get_disambiguated_names(selected_curves)
        slope_window_overlay = self._build_slope_window_overlay()
        
        plot_overview(
            self.window.overview_figure,
            selected_curves,
            self.state,
            display_names,
            slope_window_overlay=slope_window_overlay
        )
        self.window.overview_canvas.draw()
    
    def _update_detail_plot(self, result: CalcResult):
        """Update the detail plot for a calculation result."""
        # Find the curve
        curve = None
        for c in self.state.curves:
            if c.path == result.curve_path:
                curve = c
                break
        
        if curve is None:
            logger.warning("Curve not found for detail plot: %s", result.curve_path)
            return

        # Store full range for popup
        try:
            df = curve.raw_df
            self.window.set_detail_full_range(df['Temp_C'].values, df['Mass_pct'].values)
        except Exception:
            pass

        # Store context for popup rebuild
        slope_overlay = self._build_detail_slope_window_overlay(curve, result)
        self.window.set_detail_context(curve, result, slope_overlay)

        plot_detail(self.window.detail_figure, curve, result,
                    slope_window_overlay=slope_overlay)
        self.window.detail_canvas.draw()
    
    # =========================================================================
    # Ranges and Calculations
    # =========================================================================
    
    def _on_add_range(self):
        """Add a new calculation range."""
        self.window.add_range_row()
        logger.debug("Added new range row")
    
    def _on_duplicate_range(self):
        """Duplicate selected range."""
        row = self.window.get_selected_range_row()
        if row < 0:
            return
        
        ranges = self.window.get_ranges_data()
        if row < len(ranges):
            r = ranges[row]
            self.window.add_range_row(
                r['start_temp'], r['end_temp'],
                r['method'], r.get('curve_index')
            )
            logger.debug("Duplicated range row %d", row)
    
    def _on_remove_range(self):
        """Remove selected range."""
        row = self.window.get_selected_range_row()
        if row >= 0:
            self.window.ranges_table.removeRow(row)
            logger.debug("Removed range row %d", row)
    
    def _on_clear_ranges(self):
        """Clear all ranges."""
        self.window.ranges_table.setRowCount(0)
        logger.debug("Cleared all ranges")
    
    def _on_calculate(self):
        """Run calculations for all ranges on selected curves."""
        ranges = self.window.get_ranges_data()
        if not ranges:
            QMessageBox.warning(
                self.window,
                "No Ranges",
                "Please add at least one calculation range."
            )
            return
        
        logger.info("Running calculations for %d ranges", len(ranges))
        
        missing_curve = False
        last_result_index = None
        
        for r in ranges:
            try:
                curve_index = r.get('curve_index')
                if curve_index is None or curve_index >= len(self.state.curves):
                    missing_curve = True
                    continue
                curve = self.state.curves[curve_index]
                df = curve.raw_df
                temp = df['Temp_C'].values
                mass_raw = df['Mass_pct'].values

                # Select which mass series to use
                if self.state.calc_use_series == UseSeries.SMOOTHED_TG:
                    if self.state.tg_smoothing.enabled:
                        mass_smooth, _ = smooth_series(
                            mass_raw,
                            self.state.tg_smoothing.window,
                            self.state.tg_smoothing.poly
                        )
                    else:
                        mass_smooth = mass_raw
                    mass = mass_smooth
                    smoothing_params = {
                        'enabled': self.state.tg_smoothing.enabled,
                        'window': self.state.tg_smoothing.window,
                        'poly': self.state.tg_smoothing.poly
                    } if self.state.tg_smoothing.enabled else None
                else:
                    mass = mass_raw
                    smoothing_params = None
                
                # Run calculation
                result = calculate_mass_loss(
                    temp, mass,
                    r['start_temp'], r['end_temp'],
                    r['method'],
                    self.state.calc_window_pts_left,
                    self.state.calc_window_pts_right,
                    self.state.marsh_turning_fraction
                )
                
                if not result.is_valid:
                    logger.error("Invalid calculation: %s", result.error_message)
                    QMessageBox.warning(
                        self.window,
                        "Calculation Error",
                        f"Invalid range: {r['start_temp']} - {r['end_temp']}\n{result.error_message}"
                    )
                    continue
                
                # Create CalcResult
                method_enum = {
                    'Stepwise': CalcMethod.STEPWISE,
                    'Software': CalcMethod.SOFTWARE,
                    'Tangential-Marsh': CalcMethod.TANGENTIAL_MARSH
                }.get(r['method'], CalcMethod.STEPWISE)
                
                calc_result = CalcResult(
                    timestamp=datetime.now(),
                    curve_name=curve.name,
                    curve_path=curve.path,
                    method=method_enum,
                    start_temp=r['start_temp'],
                    end_temp=r['end_temp'],
                    use_series=self.state.calc_use_series,
                    delta_y=result.delta_y,
                    params=result.params,
                    details=result.details,
                    smoothing_params=smoothing_params
                )
                
                self.state.calc_results.append(calc_result)
                self._range_result_index[r['row']] = len(self.state.calc_results) - 1
                
                # Add to results table
                last_result_index = self.window.add_result_row({
                    'timestamp': calc_result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'curve_name': calc_result.curve_name,
                    'method': calc_result.method.value,
                    'start_temp': calc_result.start_temp,
                    'end_temp': calc_result.end_temp,
                    'use_series': calc_result.use_series.value,
                    'delta_y': calc_result.delta_y,
                    'window_pts_left': result.params.get('window_pts_left', ''),
                    'window_pts_right': result.params.get('window_pts_right', ''),
                    'turning_temp': f"{result.params.get('turning_temp', ''):.1f}" if result.params.get('turning_temp') else '',
                    'details': result.details[:100] + '...' if len(result.details) > 100 else result.details
                })

                # Update quick delta in ranges table
                self.window.set_range_delta(r['row'], calc_result.delta_y)

                # Log calculation to CSV
                append_calculation_log({
                    'timestamp': calc_result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'curve_name': calc_result.curve_name,
                    'curve_path': calc_result.curve_path,
                    'method': calc_result.method.value,
                    'start_temp': calc_result.start_temp,
                    'end_temp': calc_result.end_temp,
                    'use_series': calc_result.use_series.value,
                    'delta_y': f"{calc_result.delta_y:.6f}",
                    'slope_window_lower': str(result.params.get('window_pts_left', '')),
                    'slope_window_upper': str(result.params.get('window_pts_right', '')),
                    'turning_temp': f"{result.params.get('turning_temp', ''):.1f}" if result.params.get('turning_temp') else '',
                    'details': result.details
                })
                
                logger.info("Calculation complete: %s, ΔY = %.4f%%", 
                           r['method'], result.delta_y)
                
            except Exception as e:
                logger.error("Calculation failed: %s", str(e), exc_info=True)
                QMessageBox.warning(
                    self.window,
                    "Calculation Error",
                    f"Error calculating range {r['start_temp']} - {r['end_temp']}:\n{str(e)}"
                )

        if missing_curve:
            QMessageBox.warning(
                self.window,
                "Curve Missing",
                "Please select a curve for each range."
            )

        if last_result_index is not None:
            self.window.select_result_row(last_result_index)
            self._update_detail_plot(self.state.calc_results[last_result_index])

    def _on_range_selected(self, row: int):
        """Show detail plot for the selected range row (if calculated)."""
        if self.state.show_slope_window_preview:
            self._update_plot()

        result_index = self._range_result_index.get(row)
        if result_index is None or result_index >= len(self.state.calc_results):
            return
        result = self.state.calc_results[result_index]
        self._update_detail_plot(result)
    
    def _on_result_selected(self, row: int):
        """Handle result row selection - show detail plot."""
        if row < 0 or row >= len(self.state.calc_results):
            return
        
        result = self.state.calc_results[row]
        self._update_detail_plot(result)
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def _on_export_results(self, format_type: str):
        """Export results to file."""
        if not self.state.calc_results:
            QMessageBox.warning(
                self.window,
                "No Results",
                "No results to export."
            )
            return
        
        if format_type == 'tsv':
            filepath, _ = QFileDialog.getSaveFileName(
                self.window,
                "Export Results as TSV",
                "results.tsv",
                "TSV Files (*.tsv);;All Files (*)"
            )
            if filepath:
                self._export_tsv(filepath)
        else:
            filepath, _ = QFileDialog.getSaveFileName(
                self.window,
                "Export Results as JSON",
                "results.json",
                "JSON Files (*.json);;All Files (*)"
            )
            if filepath:
                self._export_json(filepath)
    
    def _export_tsv(self, filepath: str):
        """Export results to TSV file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Header
                headers = [
                    'Timestamp', 'Curve', 'CurvePath', 'Method',
                    'StartTemp', 'EndTemp', 'UseSeries', 'DeltaY',
                    'SlopeWindowLower', 'SlopeWindowUpper', 'TurningTemp', 'Details'
                ]
                f.write('\t'.join(headers) + '\n')
                
                # Data rows
                for result in self.state.calc_results:
                    turning_temp = result.params.get('turning_temp') if isinstance(result.params, dict) else None
                    turning_temp_text = f"{turning_temp:.1f}" if isinstance(turning_temp, (int, float)) else ""
                    row = [
                        result.timestamp.isoformat(),
                        result.curve_name,
                        result.curve_path,
                        result.method.value,
                        str(result.start_temp),
                        str(result.end_temp),
                        result.use_series.value,
                        f"{result.delta_y:.6f}",
                        str(result.params.get('window_pts_left', '')),
                        str(result.params.get('window_pts_right', '')),
                        turning_temp_text,
                        result.details.replace('\n', ' ')
                    ]
                    f.write('\t'.join(row) + '\n')
            
            logger.info("Exported results to TSV: %s", filepath)
            QMessageBox.information(
                self.window,
                "Export Complete",
                f"Results exported to:\n{filepath}"
            )
        except Exception as e:
            logger.error("TSV export failed: %s", str(e))
            QMessageBox.warning(
                self.window,
                "Export Failed",
                f"Failed to export TSV:\n{str(e)}"
            )
    
    def _export_json(self, filepath: str):
        """Export results to JSON file with full reproducibility metadata."""
        try:
            data = {
                'export_timestamp': datetime.now().isoformat(),
                'app_version': '1.0.0',
                'results': [result.to_dict() for result in self.state.calc_results]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("Exported results to JSON: %s", filepath)
            QMessageBox.information(
                self.window,
                "Export Complete",
                f"Results exported to:\n{filepath}"
            )
        except Exception as e:
            logger.error("JSON export failed: %s", str(e))
            QMessageBox.warning(
                self.window,
                "Export Failed",
                f"Failed to export JSON:\n{str(e)}"
            )
    
    # =========================================================================
    # Raw Data Preview
    # =========================================================================
    
    def _on_include_derived_changed(self, checked: bool):
        """Handle include derived columns checkbox change."""
        self._update_raw_data_preview()
    
    def _on_raw_data_curve_changed(self, index: int):
        """Handle raw data curve selection change."""
        self._update_raw_data_preview()
    
    def _update_raw_data_preview(self):
        """Update the raw data preview table."""
        idx = self.window.get_raw_data_curve_index()
        
        if idx is None or idx >= len(self.state.curves):
            self.window.update_raw_data_table(None)
            return
        
        curve = self.state.curves[idx]
        df = curve.raw_df.copy()
        
        # Add derived columns if requested
        if self.window.include_derived_checkbox.isChecked():
            try:
                # Get x based on current mode
                if self.state.x_axis_mode == XAxisMode.TEMPERATURE:
                    x = df['Temp_C'].values
                else:
                    x = df['Time_min'].values
                
                mass = df['Mass_pct'].values
                
                # Compute DTG raw
                dtg_result = compute_dtg(x, mass)
                df['dtg_raw'] = dtg_result.dtg
                
                # Compute DTG smooth
                if self.state.dtg_smoothing.enabled:
                    dtg_smooth, _ = smooth_series(
                        dtg_result.dtg,
                        self.state.dtg_smoothing.window,
                        self.state.dtg_smoothing.poly
                    )
                    df['dtg_smooth'] = dtg_smooth
                
                # Compute TG smooth
                if self.state.tg_smoothing.enabled:
                    tg_smooth, _ = smooth_series(
                        mass,
                        self.state.tg_smoothing.window,
                        self.state.tg_smoothing.poly
                    )
                    df['tg_smooth'] = tg_smooth
                    
            except Exception as e:
                logger.warning("Failed to compute derived columns: %s", str(e))
        
        self.window.update_raw_data_table(df)
    
    # =========================================================================
    # Save/Load Configuration
    # =========================================================================
    
    def _on_save_config(self):
        """Save current configuration to a JSON file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Configuration",
            "tga_config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return
        
        try:
            ranges = self.window.get_ranges_data()
            for r in ranges:
                delta_item = self.window.ranges_table.item(r['row'], 4)
                if delta_item is not None:
                    text = delta_item.text().strip()
                    try:
                        r['delta_y'] = float(text)
                    except ValueError:
                        r['delta_y'] = text
                else:
                    r['delta_y'] = ""

            config = {
                'version': '1.0',
                'curves': [
                    {'path': c.path, 'name': c.name}
                    for c in self.state.curves
                ],
                'selected_curve_indices': self.state.selected_curve_indices,
                'settings': {
                    'x_axis_mode': self.state.x_axis_mode.value,
                    'show_tg': self.state.show_tg,
                    'show_dtg': self.state.show_dtg,
                    'normalize_at_40': self.state.normalize_at_40,
                    'overlay_raw': self.state.overlay_raw,
                    'show_slope_window_preview': self.state.show_slope_window_preview,
                    'calc_use_series': self.state.calc_use_series.value,
                    'calc_window_pts_left': self.state.calc_window_pts_left,
                    'calc_window_pts_right': self.state.calc_window_pts_right,
                    'marsh_turning_fraction': self.state.marsh_turning_fraction,
                    'dtg_smoothing': {
                        'enabled': self.state.dtg_smoothing.enabled,
                        'window': self.state.dtg_smoothing.window,
                        'poly': self.state.dtg_smoothing.poly,
                    },
                    'tg_smoothing': {
                        'enabled': self.state.tg_smoothing.enabled,
                        'window': self.state.tg_smoothing.window,
                        'poly': self.state.tg_smoothing.poly,
                    },
                },
                'ranges': ranges,
                'range_result_index': {str(k): v for k, v in self._range_result_index.items()},
                'results': [r.to_dict() for r in self.state.calc_results],
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info("Configuration saved to: %s", filepath)
            QMessageBox.information(
                self.window,
                "Save Complete",
                f"Configuration saved to:\n{filepath}"
            )
        except Exception as e:
            logger.error("Failed to save configuration: %s", str(e))
            QMessageBox.warning(
                self.window,
                "Save Failed",
                f"Failed to save configuration:\n{str(e)}"
            )
    
    def _on_load_config(self):
        """Load configuration from a JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self.window,
            "Load Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Clear current state
            self.state.clear_curves()
            self.state.calc_results.clear()
            self._range_result_index.clear()
            
            # Load curves
            missing_files = []
            for curve_info in config.get('curves', []):
                path = curve_info['path']
                if os.path.exists(path):
                    curve, warnings = load_tga_file(path, self.window)
                    if curve is not None:
                        self.state.add_curve(curve)
                    else:
                        missing_files.append(path)
                else:
                    missing_files.append(path)
            
            # Restore selected indices (within bounds)
            saved_indices = config.get('selected_curve_indices', [])
            self.state.selected_curve_indices = [
                i for i in saved_indices if i < len(self.state.curves)
            ]
            
            # Restore settings
            settings = config.get('settings', {})
            self.state.x_axis_mode = XAxisMode(settings.get('x_axis_mode', 'Temperature'))
            self.state.show_tg = settings.get('show_tg', True)
            self.state.show_dtg = settings.get('show_dtg', True)
            self.state.normalize_at_40 = settings.get('normalize_at_40', False)
            self.state.overlay_raw = settings.get('overlay_raw', False)
            self.state.show_slope_window_preview = settings.get('show_slope_window_preview', False)
            self.state.calc_use_series = UseSeries(settings.get('calc_use_series', 'Raw TG'))
            self.state.calc_window_pts_left = settings.get('calc_window_pts_left', 30)
            self.state.calc_window_pts_right = settings.get('calc_window_pts_right', 30)
            self.state.marsh_turning_fraction = settings.get('marsh_turning_fraction', 0.5)
            self.window.filter_edit.setText("")
            
            dtg_s = settings.get('dtg_smoothing', {})
            self.state.dtg_smoothing = SmoothingParams(
                enabled=dtg_s.get('enabled', True),
                window=dtg_s.get('window', 201),
                poly=dtg_s.get('poly', 3)
            )
            
            tg_s = settings.get('tg_smoothing', {})
            self.state.tg_smoothing = SmoothingParams(
                enabled=tg_s.get('enabled', False),
                window=tg_s.get('window', 201),
                poly=tg_s.get('poly', 3)
            )
            
            # Update UI controls to match loaded state
            self._update_ui_from_state()
            
            # Clear and restore ranges
            self.window.ranges_table.setRowCount(0)
            range_curve_indices = set()
            for r in config.get('ranges', []):
                curve_index = r.get('curve_index')
                if isinstance(curve_index, int) and curve_index < len(self.state.curves):
                    range_curve_indices.add(curve_index)
                self.window.add_range_row(
                    r.get('start_temp', 100),
                    r.get('end_temp', 200),
                    r.get('method', 'Stepwise'),
                    r.get('curve_index')
                )
                row_idx = self.window.ranges_table.rowCount() - 1
                delta_y = r.get('delta_y', "")
                if isinstance(delta_y, (int, float)):
                    self.window.set_range_delta(row_idx, float(delta_y))
                elif isinstance(delta_y, str) and delta_y.strip():
                    try:
                        self.window.set_range_delta(row_idx, float(delta_y))
                    except ValueError:
                        pass
            
            # Restore results
            self.window.results_table.setRowCount(0)
            self.state.calc_results.clear()
            for result_dict in config.get('results', []):
                try:
                    method_str = result_dict.get('method', CalcMethod.STEPWISE.value)
                    method_enum = next(
                        (m for m in CalcMethod if m.value == method_str),
                        CalcMethod.STEPWISE
                    )
                    use_series_str = result_dict.get('use_series', UseSeries.RAW_TG.value)
                    use_series_enum = next(
                        (u for u in UseSeries if u.value == use_series_str),
                        UseSeries.RAW_TG
                    )
                    params = result_dict.get('params') or {}
                    if not isinstance(params, dict):
                        params = {}
                    turning_temp = params.get('turning_temp')
                    turning_temp_text = f"{turning_temp:.1f}" if isinstance(turning_temp, (int, float)) else ""

                    calc_result = CalcResult(
                        timestamp=datetime.fromisoformat(result_dict.get('timestamp')),
                        curve_name=result_dict.get('curve_name', ''),
                        curve_path=result_dict.get('curve_path', ''),
                        method=method_enum,
                        start_temp=result_dict.get('start_temp', 0.0),
                        end_temp=result_dict.get('end_temp', 0.0),
                        use_series=use_series_enum,
                        delta_y=result_dict.get('delta_y', 0.0),
                        params=params,
                        details=result_dict.get('details', ''),
                        smoothing_params=result_dict.get('smoothing_params')
                    )
                    self.state.calc_results.append(calc_result)
                    self.window.add_result_row({
                        'timestamp': calc_result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'curve_name': calc_result.curve_name,
                        'method': calc_result.method.value,
                        'start_temp': calc_result.start_temp,
                        'end_temp': calc_result.end_temp,
                        'use_series': calc_result.use_series.value,
                        'delta_y': calc_result.delta_y,
                        'window_pts_left': params.get('window_pts_left', ''),
                        'window_pts_right': params.get('window_pts_right', ''),
                        'turning_temp': turning_temp_text,
                        'details': calc_result.details[:100] + '...' if len(calc_result.details) > 100 else calc_result.details
                    })
                except Exception:
                    logger.warning("Failed to restore a result from config", exc_info=True)

            self._range_result_index = {
                int(k): int(v)
                for k, v in (config.get('range_result_index') or {}).items()
                if isinstance(v, int) or (isinstance(v, str) and v.isdigit())
            }
            
            # Ensure curves referenced by ranges are selectable in combos
            if range_curve_indices:
                merged = set(self.state.selected_curve_indices) | range_curve_indices
                self.state.selected_curve_indices = sorted(merged)

            self._invalidate_cache()
            self._refresh_ui()

            # Re-apply curve selections for range rows
            for row_idx, r in enumerate(config.get('ranges', [])):
                curve_index = r.get('curve_index')
                if isinstance(curve_index, int):
                    self.window.set_range_curve_selection(row_idx, curve_index)
            
            msg = f"Configuration loaded from:\n{filepath}"
            if missing_files:
                msg += f"\n\nCould not load {len(missing_files)} file(s):\n"
                msg += "\n".join(missing_files[:5])
                if len(missing_files) > 5:
                    msg += f"\n... and {len(missing_files) - 5} more"
            
            logger.info("Configuration loaded from: %s", filepath)
            QMessageBox.information(
                self.window,
                "Load Complete",
                msg
            )
        except Exception as e:
            logger.error("Failed to load configuration: %s", str(e))
            QMessageBox.warning(
                self.window,
                "Load Failed",
                f"Failed to load configuration:\n{str(e)}"
            )
    
    def _update_ui_from_state(self):
        """Update UI controls to match current state."""
        w = self.window
        
        # Block signals while updating
        w.show_tg_checkbox.blockSignals(True)
        w.show_dtg_checkbox.blockSignals(True)
        w.xaxis_temp_radio.blockSignals(True)
        w.xaxis_time_radio.blockSignals(True)
        w.normalize_checkbox.blockSignals(True)
        w.overlay_raw_checkbox.blockSignals(True)
        w.btn_show_slope_window.blockSignals(True)
        w.calc_series_combo.blockSignals(True)
        w.calc_window_pts_left_spin.blockSignals(True)
        w.calc_window_pts_right_spin.blockSignals(True)
        w.marsh_turning_frac_spin.blockSignals(True)
        w.dtg_smooth_checkbox.blockSignals(True)
        w.dtg_window_spin.blockSignals(True)
        w.dtg_poly_spin.blockSignals(True)
        w.tg_smooth_checkbox.blockSignals(True)
        w.tg_window_spin.blockSignals(True)
        w.tg_poly_spin.blockSignals(True)
        
        # Set values
        w.show_tg_checkbox.setChecked(self.state.show_tg)
        w.show_dtg_checkbox.setChecked(self.state.show_dtg)
        w.xaxis_temp_radio.setChecked(self.state.x_axis_mode == XAxisMode.TEMPERATURE)
        w.xaxis_time_radio.setChecked(self.state.x_axis_mode == XAxisMode.TIME)
        w.normalize_checkbox.setChecked(self.state.normalize_at_40)
        w.overlay_raw_checkbox.setChecked(self.state.overlay_raw)
        w.btn_show_slope_window.setChecked(self.state.show_slope_window_preview)
        w.calc_series_combo.setCurrentText(self.state.calc_use_series.value)
        w.calc_window_pts_left_spin.setValue(self.state.calc_window_pts_left)
        w.calc_window_pts_right_spin.setValue(self.state.calc_window_pts_right)
        w.marsh_turning_frac_spin.setValue(int(self.state.marsh_turning_fraction * 100))
        
        w.dtg_smooth_checkbox.setChecked(self.state.dtg_smoothing.enabled)
        w.dtg_window_spin.setValue(self.state.dtg_smoothing.window)
        w.dtg_poly_spin.setValue(self.state.dtg_smoothing.poly)
        
        w.tg_smooth_checkbox.setChecked(self.state.tg_smoothing.enabled)
        w.tg_window_spin.setValue(self.state.tg_smoothing.window)
        w.tg_poly_spin.setValue(self.state.tg_smoothing.poly)
        
        # Unblock signals
        w.show_tg_checkbox.blockSignals(False)
        w.show_dtg_checkbox.blockSignals(False)
        w.xaxis_temp_radio.blockSignals(False)
        w.xaxis_time_radio.blockSignals(False)
        w.normalize_checkbox.blockSignals(False)
        w.overlay_raw_checkbox.blockSignals(False)
        w.btn_show_slope_window.blockSignals(False)
        w.calc_series_combo.blockSignals(False)
        w.calc_window_pts_left_spin.blockSignals(False)
        w.calc_window_pts_right_spin.blockSignals(False)
        w.marsh_turning_frac_spin.blockSignals(False)
        w.dtg_smooth_checkbox.blockSignals(False)
        w.dtg_window_spin.blockSignals(False)
        w.dtg_poly_spin.blockSignals(False)
        w.tg_smooth_checkbox.blockSignals(False)
        w.tg_window_spin.blockSignals(False)
        w.tg_poly_spin.blockSignals(False)
