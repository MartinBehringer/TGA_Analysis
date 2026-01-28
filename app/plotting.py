"""
Plotting utilities for the TGA Analysis application.

Provides:
- Overview plot for multiple TG/DTG curves
- Detail plot for mass-loss calculation visualization
- Twin axis handling for TG/DTG simultaneous display
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from app.models import AppState, CalcMethod, CurveData, XAxisMode, CalcResult
from app.processing import (
    compute_dtg, smooth_series, normalize_mass_at_40,
    WINDOW_PTS, _find_nearest_index
)
from app.logging_setup import get_logger

logger = get_logger('plotting')


# Plot styling constants
TG_LINEWIDTH = 2.0
DTG_LINEWIDTH = 1.5
RAW_ALPHA = 0.3
MARKER_SIZE = 10
ARROW_HEAD_WIDTH = 0.3
DETAIL_BUFFER = 20.0  # °C buffer around calculation range

# Modern color palette (clean, professional)
COLORS = ['#0066cc', '#ff3b30', '#34c759', '#ff9500', '#af52de', '#00c7be', '#ff6482', '#5856d6']


def apply_figure_style(fig: Figure):
    """Apply light theme styling to a figure."""
    fig.patch.set_facecolor('#ffffff')
    for ax in fig.get_axes():
        ax.set_facecolor('#ffffff')
        ax.tick_params(colors='#86868b', which='both')
        ax.xaxis.label.set_color('#1d1d1f')
        ax.yaxis.label.set_color('#1d1d1f')
        ax.title.set_color('#1d1d1f')
        for spine in ax.spines.values():
            spine.set_color('#d1d1d6')


def get_disambiguated_names(curves: List[CurveData]) -> List[str]:
    """
    Generate unique display names for curves, disambiguating duplicates.
    Removes file extension from names.
    
    If multiple curves have the same base filename, append "(2)", "(3)", etc.
    
    Args:
        curves: List of CurveData objects
        
    Returns:
        List of unique display names without file extensions
    """
    import os
    name_counts: Dict[str, int] = {}
    names: List[str] = []
    
    for curve in curves:
        # Remove file extension
        base_name = os.path.splitext(curve.name)[0]
        if base_name in name_counts:
            name_counts[base_name] += 1
            names.append(f"{base_name} ({name_counts[base_name]})")
        else:
            name_counts[base_name] = 1
            names.append(base_name)
    
    return names


def plot_overview(
    fig: Figure,
    curves: List[CurveData],
    state: AppState,
    display_names: Optional[List[str]] = None
) -> None:
    """
    Plot overview of multiple TG/DTG curves.
    
    Handles:
    - TG-only, DTG-only, or both (twin axis)
    - Temperature or Time x-axis
    - Normalization at 40°C
    - Smoothing for TG and DTG
    - Overlay of raw series behind smoothed
    
    Args:
        fig: Matplotlib figure to plot on
        curves: List of curves to plot
        state: Application state with plot settings
        display_names: Optional list of display names for legend
    """
    fig.clear()
    
    if not curves:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No curves loaded", ha='center', va='center', 
                transform=ax.transAxes, fontsize=14, color='#86868b')
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel("Mass (%)")
        apply_figure_style(fig)
        fig.tight_layout()
        return
    
    if display_names is None:
        display_names = get_disambiguated_names(curves)
    
    # Determine axis setup
    show_tg = state.show_tg
    show_dtg = state.show_dtg
    
    if not show_tg and not show_dtg:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No series selected for display", ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='#86868b')
        apply_figure_style(fig)
        fig.tight_layout()
        return
    
    ax = fig.add_subplot(111)
    ax2 = None
    
    if show_tg and show_dtg:
        ax2 = ax.twinx()
    
    # Use our custom color palette
    colors = [COLORS[i % len(COLORS)] for i in range(len(curves))]
    
    # X-axis configuration
    x_mode = state.x_axis_mode
    if x_mode == XAxisMode.TEMPERATURE:
        x_col = 'Temp_C'
        x_label = "Temperature (°C)"
        dtg_unit = "%/°C"
    else:
        x_col = 'Time_min'
        x_label = "Time (min)"
        dtg_unit = "%/min"
    
    # Track legend entries - one per curve (not separate TG/DTG)
    legend_handles: List[Line2D] = []
    legend_labels: List[str] = []
    
    for i, (curve, name, color) in enumerate(zip(curves, display_names, colors)):
        df = curve.raw_df
        x = df[x_col].values
        mass_raw = df['Mass_pct'].values
        
        # Apply normalization if enabled
        if state.normalize_at_40:
            try:
                mass_display, _, _ = normalize_mass_at_40(df['Temp_C'].values, mass_raw)
            except ValueError:
                mass_display = mass_raw
        else:
            mass_display = mass_raw
        
        # TG smoothing
        if state.tg_smoothing.enabled:
            tg_smooth, _ = smooth_series(
                mass_display, 
                state.tg_smoothing.window, 
                state.tg_smoothing.poly
            )
        else:
            tg_smooth = mass_display
        
        # Compute DTG
        dtg_result = compute_dtg(x, mass_display, x_label.split()[0])
        dtg_raw = dtg_result.dtg
        
        # DTG smoothing
        if state.dtg_smoothing.enabled:
            dtg_display, _ = smooth_series(
                dtg_raw, 
                state.dtg_smoothing.window, 
                state.dtg_smoothing.poly
            )
        else:
            dtg_display = dtg_raw
        
        # Plot TG
        if show_tg:
            # Overlay raw if enabled and smoothing is active
            if state.overlay_raw and state.tg_smoothing.enabled:
                ax.plot(x, mass_display, color=color, alpha=RAW_ALPHA, 
                       linewidth=TG_LINEWIDTH, linestyle='--')
            
            line, = ax.plot(x, tg_smooth, color=color, linewidth=TG_LINEWIDTH, label=name)
            # Only add to legend if not already added (single entry per curve)
            if name not in legend_labels:
                legend_handles.append(line)
                legend_labels.append(name)
        
        # Plot DTG
        if show_dtg:
            dtg_ax = ax2 if ax2 is not None else ax
            
            # Overlay raw if enabled and smoothing is active
            if state.overlay_raw and state.dtg_smoothing.enabled:
                dtg_ax.plot(x, dtg_raw, color=color, alpha=RAW_ALPHA,
                           linewidth=DTG_LINEWIDTH, linestyle=':')
            
            line, = dtg_ax.plot(x, dtg_display, color=color, linewidth=DTG_LINEWIDTH,
                               linestyle='--' if show_tg else '-')
            # Only add to legend if TG wasn't shown (single entry per curve)
            if not show_tg and name not in legend_labels:
                legend_handles.append(line)
                legend_labels.append(name)
    
    # Configure axes
    ax.set_xlabel(x_label)
    
    if show_tg and show_dtg:
        ax.set_ylabel("Mass (%)", color='#1d1d1f')
        ax2.set_ylabel(f"DTG ({dtg_unit})", color='#555555')
        ax2.tick_params(axis='y', labelcolor='#555555')
        for spine in ax2.spines.values():
            spine.set_color('#d1d1d6')
    elif show_tg:
        ax.set_ylabel("Mass (%)")
    else:
        ax.set_ylabel(f"DTG ({dtg_unit})")
    
    # Single legend for all curves, positioned center right
    if legend_handles:
        legend = ax.legend(legend_handles, legend_labels, loc='center right', fontsize=9,
                          facecolor='#ffffff', edgecolor='#e5e5e7', labelcolor='#1d1d1f')
    
    ax.grid(True, alpha=0.5, color='#e5e5e7')
    apply_figure_style(fig)
    fig.tight_layout()
    
    logger.debug("Plotted overview: %d curves, show_tg=%s, show_dtg=%s", 
                len(curves), show_tg, show_dtg)


def plot_detail(
    fig: Figure,
    curve: CurveData,
    result: CalcResult,
    buffer: float = DETAIL_BUFFER,
    full_range: bool = False
) -> None:
    """
    Plot detailed view of a mass-loss calculation result.
    
    Shows:
    - TG curve segment around the calculation range
    - Markers at T_start and T_end
    - Method-specific visualization:
      - Stepwise: horizontal lines + vertical arrow
      - Software: parallel tangent lines + vertical arrow at midpoint
      - Tangential-Marsh: both tangent lines + vertical line at turning temp + arrow
    
    Args:
        fig: Matplotlib figure to plot on
        curve: CurveData for the curve
        result: CalcResult with calculation parameters
        buffer: Temperature buffer around range (°C)
    """
    fig.clear()
    ax = fig.add_subplot(111)
    
    df = curve.raw_df
    temp = df['Temp_C'].values
    mass = df['Mass_pct'].values
    
    params = result.params
    t_start = result.start_temp
    t_end = result.end_temp
    
    # Define plot range with buffer
    if full_range:
        t_min = temp.min()
        t_max = temp.max()
    else:
        t_min = max(temp.min(), t_start - buffer)
        t_max = min(temp.max(), t_end + buffer)
    
    # Filter data to range
    mask = (temp >= t_min) & (temp <= t_max)
    temp_range = temp[mask]
    mass_range = mass[mask]
    
    if len(temp_range) == 0:
        ax.text(0.5, 0.5, "No data in selected range", ha='center', va='center',
                transform=ax.transAxes, color='#86868b')
        apply_figure_style(fig)
        fig.tight_layout()
        return
    
    # Plot TG curve segment or full curve
    if full_range:
        ax.plot(temp, mass, color='#0066cc', linewidth=TG_LINEWIDTH, label='TG')
    else:
        ax.plot(temp_range, mass_range, color='#0066cc', linewidth=TG_LINEWIDTH, label='TG')
    
    # Get actual points from params
    idx_start = params.get('idx_start', _find_nearest_index(temp, t_start))
    idx_end = params.get('idx_end', _find_nearest_index(temp, t_end))
    
    t_start_actual = temp[idx_start]
    t_end_actual = temp[idx_end]
    mass_start = mass[idx_start]
    mass_end = mass[idx_end]
    
    # Mark start and end points
    ax.plot(t_start_actual, mass_start, 'o', color='#34c759', markersize=MARKER_SIZE, label='T_start')
    ax.plot(t_end_actual, mass_end, 'o', color='#ff3b30', markersize=MARKER_SIZE, label='T_end')
    
    delta_y = result.delta_y
    method = result.method
    
    if method == CalcMethod.STEPWISE:
        _plot_stepwise_detail(ax, t_start_actual, t_end_actual, mass_start, mass_end, delta_y)
    elif method == CalcMethod.SOFTWARE:
        _plot_software_detail(ax, params, t_min, t_max, delta_y)
    elif method == CalcMethod.TANGENTIAL_MARSH:
        _plot_marsh_detail(ax, params, t_min, t_max, delta_y)
    
    # Labels and title
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Mass (%)")
    ax.set_title(f"{method.value}: ΔY = {delta_y:.3f}%", color='#1d1d1f', fontweight='bold')
    ax.legend(loc='best', fontsize=9, facecolor='#ffffff', edgecolor='#e5e5e7', labelcolor='#1d1d1f')
    ax.grid(True, alpha=0.5, color='#e5e5e7')
    
    apply_figure_style(fig)
    fig.tight_layout()
    logger.debug("Plotted detail: method=%s, delta_y=%.4f", method.value, delta_y)


def _plot_stepwise_detail(
    ax: Axes,
    t_start: float,
    t_end: float,
    mass_start: float,
    mass_end: float,
    delta_y: float
) -> None:
    """
    Add Stepwise method visualization.
    
    Shows:
    - Horizontal guide lines at both mass values
    - Vertical double-arrow showing ΔY at midpoint
    """
    t_mid = (t_start + t_end) / 2
    
    # Horizontal lines
    ax.axhline(y=mass_start, color='#34c759', linestyle='--', alpha=0.6)
    ax.axhline(y=mass_end, color='#ff3b30', linestyle='--', alpha=0.6)
    
    # Vertical arrow showing ΔY
    ax.annotate(
        '', xy=(t_mid, mass_end), xytext=(t_mid, mass_start),
        arrowprops=dict(arrowstyle='<->', color='#af52de', lw=2)
    )
    
    # Label
    y_mid = (mass_start + mass_end) / 2
    ax.text(t_mid + 5, y_mid, f'ΔY = {delta_y:.2f}%', 
            fontsize=11, color='#af52de', fontweight='bold')


def _plot_software_detail(
    ax: Axes,
    params: Dict[str, Any],
    t_min: float,
    t_max: float,
    delta_y: float
) -> None:
    """
    Add Software (parallel tangent) method visualization.
    
    Shows:
    - Two parallel lines with the chosen slope
    - Vertical arrow at midpoint showing ΔY
    """
    m = params.get('m', 0)
    b1 = params.get('b1', 0)
    b2 = params.get('b2', 0)
    t_start = params.get('temp_start_actual', t_min)
    t_end = params.get('temp_end_actual', t_max)
    
    # Create line arrays
    t_line = np.array([t_min, t_max])
    y1_line = m * t_line + b1
    y2_line = m * t_line + b2
    
    # Plot parallel lines
    ax.plot(t_line, y1_line, '--', color='#34c759', linewidth=1.5, alpha=0.8, label='Tangent (start)')
    ax.plot(t_line, y2_line, '--', color='#ff3b30', linewidth=1.5, alpha=0.8, label='Tangent (end)')
    
    # Vertical arrow at midpoint
    t_mid = (t_start + t_end) / 2
    y1_mid = m * t_mid + b1
    y2_mid = m * t_mid + b2
    
    ax.annotate(
        '', xy=(t_mid, min(y1_mid, y2_mid)), xytext=(t_mid, max(y1_mid, y2_mid)),
        arrowprops=dict(arrowstyle='<->', color='#af52de', lw=2)
    )
    
    # Label
    y_label = (y1_mid + y2_mid) / 2
    ax.text(t_mid + 5, y_label, f'ΔY = {delta_y:.2f}%',
            fontsize=11, color='#af52de', fontweight='bold')
    
    # Show slope info
    slope_chosen = params.get('slope_chosen', 'unknown')
    ax.text(0.02, 0.98, f'Slope: {m:.6f} %/°C ({slope_chosen})',
            transform=ax.transAxes, fontsize=9, va='top', color='#1d1d1f',
            bbox=dict(boxstyle='round', facecolor='#ffffff', edgecolor='#e5e5e7', alpha=0.9))


def _plot_marsh_detail(
    ax: Axes,
    params: Dict[str, Any],
    t_min: float,
    t_max: float,
    delta_y: float
) -> None:
    """
    Add Tangential-Marsh method visualization.
    
    Shows:
    - Both tangent lines (different slopes)
    - Vertical line at turning temperature
    - Points where tangents intersect the turning line
    - Vertical arrow showing ΔY
    """
    m1 = params.get('m1', 0)
    m2 = params.get('m2', 0)
    b1 = params.get('b1', 0)
    b2 = params.get('b2', 0)
    turning_temp = params.get('turning_temp', (t_min + t_max) / 2)
    y1_at_turn = params.get('y1_at_turn', 0)
    y2_at_turn = params.get('y2_at_turn', 0)
    
    # Create line arrays
    t_line = np.array([t_min, t_max])
    y1_line = m1 * t_line + b1
    y2_line = m2 * t_line + b2
    
    # Plot tangent lines
    ax.plot(t_line, y1_line, '--', color='#34c759', linewidth=1.5, alpha=0.8, label='Tangent 1 (start)')
    ax.plot(t_line, y2_line, '--', color='#ff3b30', linewidth=1.5, alpha=0.8, label='Tangent 2 (end)')
    
    # Vertical line at turning temperature
    y_range = ax.get_ylim()
    ax.axvline(x=turning_temp, color='#ff9500', linestyle=':', alpha=0.6, label=f'T_turn={turning_temp:.1f}°C')
    
    # Mark intersection points
    ax.plot(turning_temp, y1_at_turn, '^', color='#34c759', markersize=MARKER_SIZE-2)
    ax.plot(turning_temp, y2_at_turn, 'v', color='#ff3b30', markersize=MARKER_SIZE-2)
    
    # Vertical arrow showing ΔY
    ax.annotate(
        '', xy=(turning_temp, min(y1_at_turn, y2_at_turn)), 
        xytext=(turning_temp, max(y1_at_turn, y2_at_turn)),
        arrowprops=dict(arrowstyle='<->', color='#af52de', lw=2)
    )
    
    # Label
    y_label = (y1_at_turn + y2_at_turn) / 2
    ax.text(turning_temp + 5, y_label, f'ΔY = {delta_y:.2f}%',
            fontsize=11, color='#af52de', fontweight='bold')
    
    # Show parameters
    info_text = f'T_turn = {turning_temp:.1f}°C\nm1 = {m1:.6f}\nm2 = {m2:.6f}'
    ax.text(0.02, 0.98, info_text,
            transform=ax.transAxes, fontsize=9, va='top', color='#1d1d1f',
            bbox=dict(boxstyle='round', facecolor='#ffffff', edgecolor='#e5e5e7', alpha=0.9))
