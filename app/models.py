"""
Data models for the TGA Analysis application.

Contains dataclasses for:
- CurveData: Represents a loaded TGA curve with metadata
- CalcRange: Defines a calculation range with method selection
- CalcResult: Stores results with full reproducibility metadata
- AppState: Global application state for UI synchronization
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd


class CalcMethod(Enum):
    """Mass-loss calculation methods."""
    STEPWISE = "Stepwise"
    SOFTWARE = "Software"
    TANGENTIAL_MARSH = "Tangential-Marsh"


class UseSeries(Enum):
    """Which TG series to use for calculations."""
    RAW_TG = "Raw TG"
    SMOOTHED_TG = "Smoothed TG"


class XAxisMode(Enum):
    """X-axis mode for plotting."""
    TEMPERATURE = "Temperature"
    TIME = "Time"


@dataclass
class ParseMetadata:
    """Metadata about how a file was parsed."""
    filetype: str = ""
    encoding: str = "ISO-8859-1"
    separator: str = ";"
    decimal: str = ","
    header_lines_skipped: int = 34
    original_columns: List[str] = field(default_factory=list)
    header_lines: List[str] = field(default_factory=list)


@dataclass
class CurveData:
    """
    Represents a loaded TGA curve with all associated data and metadata.
    
    Attributes:
        path: Full file path
        name: Display name (base filename)
        raw_df: DataFrame with canonical columns: Temp_C, Time_min, Mass_pct
        parse_metadata: Information about how the file was parsed
        parse_warnings: List of warnings generated during parsing
    """
    path: str
    name: str
    raw_df: pd.DataFrame
    parse_metadata: ParseMetadata = field(default_factory=ParseMetadata)
    parse_warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate that raw_df has required columns."""
        required_cols = {'Temp_C', 'Time_min', 'Mass_pct'}
        if not required_cols.issubset(set(self.raw_df.columns)):
            missing = required_cols - set(self.raw_df.columns)
            raise ValueError(f"raw_df missing required columns: {missing}")


@dataclass
class CalcRange:
    """
    Defines a calculation range for mass-loss computation.
    
    Attributes:
        start_temp: Start temperature in °C
        end_temp: End temperature in °C
        method: Calculation method to use
        use_series: Which TG series to use (Raw or Smoothed)
        notes: User notes for this range
    """
    start_temp: float
    end_temp: float
    method: CalcMethod = CalcMethod.STEPWISE
    use_series: UseSeries = UseSeries.RAW_TG
    notes: str = ""
    
    def is_valid(self) -> bool:
        """Check if the range is valid (start < end)."""
        return self.start_temp < self.end_temp


@dataclass
class CalcResult:
    """
    Stores calculation results with full reproducibility metadata.
    
    Attributes:
        timestamp: When the calculation was performed
        curve_name: Name of the curve used
        curve_path: Full path of the curve file
        method: Calculation method used
        start_temp: Start temperature
        end_temp: End temperature
        use_series: Which TG series was used
        delta_y: Computed mass loss in %
        params: Dict of parameters used (window_pts, slopes, etc.)
        details: Human-readable details string
        smoothing_params: Smoothing parameters at time of calculation (if applicable)
    """
    timestamp: datetime
    curve_name: str
    curve_path: str
    method: CalcMethod
    start_temp: float
    end_temp: float
    use_series: UseSeries
    delta_y: float
    params: Dict[str, Any] = field(default_factory=dict)
    details: str = ""
    smoothing_params: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'curve_name': self.curve_name,
            'curve_path': self.curve_path,
            'method': self.method.value,
            'start_temp': self.start_temp,
            'end_temp': self.end_temp,
            'use_series': self.use_series.value,
            'delta_y': self.delta_y,
            'params': self.params,
            'details': self.details,
            'smoothing_params': self.smoothing_params,
        }


@dataclass
class SmoothingParams:
    """Parameters for Savitzky-Golay smoothing."""
    enabled: bool = False
    window: int = 201
    poly: int = 3
    
    def __post_init__(self):
        """Enforce odd window."""
        if self.window % 2 == 0:
            self.window += 1


@dataclass
class AppState:
    """
    Global application state for UI synchronization.
    
    Attributes:
        curves: List of all loaded curves
        selected_curve_indices: Indices of currently selected curves
        active_curve_index: Index of the active curve for calculations
        x_axis_mode: Current x-axis mode (Temperature or Time)
        show_tg: Whether to show TG curves
        show_dtg: Whether to show DTG curves
        normalize_at_40: Whether to normalize display to 100% at 40°C
        dtg_smoothing: DTG smoothing parameters
        tg_smoothing: TG smoothing parameters
        overlay_raw: Whether to overlay raw series behind smoothed
        calc_ranges: List of calculation ranges
        calc_results: List of calculation results
    """
    curves: List[CurveData] = field(default_factory=list)
    selected_curve_indices: List[int] = field(default_factory=list)
    active_curve_index: Optional[int] = None
    x_axis_mode: XAxisMode = XAxisMode.TEMPERATURE
    show_tg: bool = True
    show_dtg: bool = True
    normalize_at_40: bool = False
    dtg_smoothing: SmoothingParams = field(default_factory=lambda: SmoothingParams(enabled=True, window=201, poly=3))
    tg_smoothing: SmoothingParams = field(default_factory=lambda: SmoothingParams(enabled=False, window=201, poly=3))
    overlay_raw: bool = False
    calc_use_series: UseSeries = UseSeries.RAW_TG
    calc_window_pts_left: int = 30
    calc_window_pts_right: int = 30
    marsh_turning_fraction: float = 0.5
    calc_ranges: List[CalcRange] = field(default_factory=list)
    calc_results: List[CalcResult] = field(default_factory=list)
    
    def get_selected_curves(self) -> List[CurveData]:
        """Get list of currently selected curves."""
        return [self.curves[i] for i in self.selected_curve_indices if i < len(self.curves)]
    
    def get_active_curve(self) -> Optional[CurveData]:
        """Get the active curve for calculations."""
        if self.active_curve_index is not None and self.active_curve_index < len(self.curves):
            return self.curves[self.active_curve_index]
        elif self.selected_curve_indices:
            return self.curves[self.selected_curve_indices[0]]
        return None
    
    def add_curve(self, curve: CurveData) -> int:
        """Add a curve and return its index."""
        self.curves.append(curve)
        return len(self.curves) - 1
    
    def remove_curve(self, index: int) -> None:
        """Remove a curve by index and update selections."""
        if 0 <= index < len(self.curves):
            self.curves.pop(index)
            # Update selected indices
            self.selected_curve_indices = [
                i - 1 if i > index else i
                for i in self.selected_curve_indices
                if i != index
            ]
            # Update active curve index
            if self.active_curve_index is not None:
                if self.active_curve_index == index:
                    self.active_curve_index = self.selected_curve_indices[0] if self.selected_curve_indices else None
                elif self.active_curve_index > index:
                    self.active_curve_index -= 1
    
    def clear_curves(self) -> None:
        """Clear all curves and reset selections."""
        self.curves.clear()
        self.selected_curve_indices.clear()
        self.active_curve_index = None
