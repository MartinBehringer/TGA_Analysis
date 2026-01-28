"""
Data processing functions for the TGA Analysis application.

Provides:
- DTG computation (derivative of mass vs temperature or time)
- Savitzky-Golay smoothing
- Normalization to 100% at 40°C
- Mass-loss calculation methods (Stepwise, Software, Tangential-Marsh)

All functions are documented with type hints and clear mathematical descriptions.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import numpy as np
from scipy.signal import savgol_filter

from app.logging_setup import get_logger

logger = get_logger('processing')


# Constants for mass-loss calculations
WINDOW_PTS = 30  # Number of points for local slope averaging


@dataclass
class DTGResult:
    """Result of DTG computation."""
    dtg: np.ndarray
    x_sorted: np.ndarray
    y_sorted: np.ndarray
    warnings: list


@dataclass
class MassLossResult:
    """Result of mass-loss calculation."""
    delta_y: float
    params: Dict[str, Any]
    details: str
    is_valid: bool
    error_message: str = ""


def compute_dtg(
    x: np.ndarray,
    y: np.ndarray,
    x_label: str = "Temperature"
) -> DTGResult:
    """
    Compute the derivative of mass (y) with respect to x using numpy.gradient.
    
    Mathematical definition:
        DTG = dy/dx = d(Mass%) / d(x)
        
    Where x can be:
        - Temperature (°C) → units: %/°C
        - Time (min) → units: %/min
    
    Handles non-monotonic x by sorting and removing duplicates.
    
    Args:
        x: Independent variable (temperature or time)
        y: Mass percentage values
        x_label: Label for logging ("Temperature" or "Time")
        
    Returns:
        DTGResult containing dtg array, sorted x/y, and warnings
    """
    warnings = []
    
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    
    if len(x) != len(y):
        raise ValueError(f"x and y must have same length: {len(x)} vs {len(y)}")
    
    if len(x) < 2:
        raise ValueError("Need at least 2 data points for DTG computation")
    
    # Check if x is monotonic
    is_increasing = np.all(np.diff(x) > 0)
    is_decreasing = np.all(np.diff(x) < 0)
    
    if not (is_increasing or is_decreasing):
        # Sort by x and handle duplicates
        sort_idx = np.argsort(x)
        x_sorted = x[sort_idx]
        y_sorted = y[sort_idx]
        
        # Remove duplicate x values (keep first)
        _, unique_idx = np.unique(x_sorted, return_index=True)
        if len(unique_idx) < len(x_sorted):
            n_dups = len(x_sorted) - len(unique_idx)
            warnings.append(f"Removed {n_dups} duplicate {x_label.lower()} values")
            logger.warning("Removed %d duplicate %s values", n_dups, x_label.lower())
        
        x_sorted = x_sorted[unique_idx]
        y_sorted = y_sorted[unique_idx]
    else:
        x_sorted = x.copy()
        y_sorted = y.copy()
        if is_decreasing:
            # Reverse to make increasing
            x_sorted = x_sorted[::-1]
            y_sorted = y_sorted[::-1]
    
    # Check x range
    x_range = x_sorted[-1] - x_sorted[0]
    if x_range < 1e-6:
        raise ValueError(f"{x_label} range too small: {x_range}")
    
    # Compute derivative using numpy.gradient
    # gradient computes (y[i+1] - y[i-1]) / (x[i+1] - x[i-1]) for interior points
    dtg = np.gradient(y_sorted, x_sorted)
    
    logger.debug("Computed DTG: %d points, x range [%.2f, %.2f]", 
                 len(dtg), x_sorted[0], x_sorted[-1])
    
    return DTGResult(
        dtg=dtg,
        x_sorted=x_sorted,
        y_sorted=y_sorted,
        warnings=warnings
    )


def smooth_series(
    y: np.ndarray,
    window: int = 201,
    poly: int = 3
) -> Tuple[np.ndarray, list]:
    """
    Apply Savitzky-Golay smoothing to a series.
    
    The Savitzky-Golay filter fits a polynomial of degree `poly` to `window` 
    consecutive data points and uses the fitted polynomial to estimate the 
    smoothed value at the center point.
    
    Args:
        y: Input array to smooth
        window: Window length (must be odd; will be adjusted if even)
        poly: Polynomial order (must be less than window)
        
    Returns:
        Tuple of (smoothed array, list of warnings)
    """
    warnings = []
    y = np.asarray(y, dtype=float)
    
    # Enforce odd window
    if window % 2 == 0:
        window += 1
        warnings.append(f"Window adjusted to odd value: {window}")
        logger.debug("Adjusted window to odd: %d", window)
    
    # Validate constraints
    if window > len(y):
        warnings.append(f"Window ({window}) > data length ({len(y)}); returning original")
        logger.warning("Window %d > data length %d; returning original", window, len(y))
        return y.copy(), warnings
    
    if window < poly + 2:
        warnings.append(f"Window ({window}) < poly+2 ({poly+2}); returning original")
        logger.warning("Window %d < poly+2 %d; returning original", window, poly + 2)
        return y.copy(), warnings
    
    if poly < 0:
        warnings.append(f"Invalid polynomial order ({poly}); returning original")
        return y.copy(), warnings
    
    try:
        smoothed = savgol_filter(y, window, poly)
        logger.debug("Applied Savitzky-Golay: window=%d, poly=%d", window, poly)
        return smoothed, warnings
    except Exception as e:
        warnings.append(f"Smoothing failed: {str(e)}; returning original")
        logger.error("Savitzky-Golay failed: %s", str(e))
        return y.copy(), warnings


def normalize_mass_at_40(
    temp: np.ndarray,
    mass: np.ndarray,
    target_temp: float = 40.0
) -> Tuple[np.ndarray, float, int]:
    """
    Normalize mass values so that Mass at target_temp (or nearest >= target_temp) = 100%.
    
    Mathematical definition:
        idx = argmin(|Temp - target_temp|) where Temp >= target_temp (preferred)
             or nearest point if none >= target_temp
        scale_factor = 100 / Mass[idx]
        Mass_normalized = Mass * scale_factor
    
    Args:
        temp: Temperature array in °C
        mass: Mass percentage array
        target_temp: Target temperature for normalization (default: 40°C)
        
    Returns:
        Tuple of (normalized mass array, scale factor, index used)
    """
    temp = np.asarray(temp, dtype=float)
    mass = np.asarray(mass, dtype=float)
    
    # Find indices where temp >= target_temp
    valid_mask = temp >= target_temp
    
    if np.any(valid_mask):
        # Find nearest temp >= target_temp
        valid_temps = temp[valid_mask]
        valid_indices = np.where(valid_mask)[0]
        nearest_in_valid = np.argmin(np.abs(valid_temps - target_temp))
        idx = valid_indices[nearest_in_valid]
    else:
        # Fallback: nearest point to target_temp
        idx = np.argmin(np.abs(temp - target_temp))
        logger.warning("No temperature >= %.1f°C found; using nearest point at %.2f°C", 
                      target_temp, temp[idx])
    
    mass_at_ref = mass[idx]
    
    if abs(mass_at_ref) < 1e-10:
        logger.error("Mass at reference point is near zero; cannot normalize")
        raise ValueError("Mass at reference point is near zero; cannot normalize")
    
    scale_factor = 100.0 / mass_at_ref
    mass_normalized = mass * scale_factor
    
    logger.debug("Normalized at Temp=%.2f°C (idx=%d): scale_factor=%.6f", 
                temp[idx], idx, scale_factor)
    
    return mass_normalized, scale_factor, idx


def _find_nearest_index(arr: np.ndarray, value: float) -> int:
    """Find index of nearest value in array."""
    return int(np.argmin(np.abs(arr - value)))


def _compute_local_slope(
    temp: np.ndarray,
    mass: np.ndarray,
    idx: int,
    window_pts: int = WINDOW_PTS
) -> float:
    """
    Compute local slope (dMass/dTemp) around an index using gradient averaging.
    
    Args:
        temp: Temperature array
        mass: Mass array
        idx: Center index for slope calculation
        window_pts: Number of points on each side to average
        
    Returns:
        Average slope in %/°C
    """
    n = len(temp)
    
    # Define window bounds
    start = max(0, idx - window_pts)
    end = min(n, idx + window_pts + 1)
    
    if end - start < 2:
        # Too few points, compute simple difference
        if idx > 0:
            return (mass[idx] - mass[idx-1]) / (temp[idx] - temp[idx-1] + 1e-10)
        elif idx < n - 1:
            return (mass[idx+1] - mass[idx]) / (temp[idx+1] - temp[idx] + 1e-10)
        else:
            return 0.0
    
    # Compute gradient in window
    temp_window = temp[start:end]
    mass_window = mass[start:end]
    
    gradients = np.gradient(mass_window, temp_window)
    
    # Return mean gradient
    return float(np.mean(gradients))


def calc_stepwise(
    temp: np.ndarray,
    mass: np.ndarray,
    t_start: float,
    t_end: float
) -> MassLossResult:
    """
    Calculate mass loss using the Stepwise (simple difference) method.
    
    Definition:
        ΔY = Mass(T_start) - Mass(T_end)
    
    Args:
        temp: Temperature array in °C
        mass: Mass percentage array
        t_start: Start temperature
        t_end: End temperature
        
    Returns:
        MassLossResult with computed delta_y and parameters
    """
    logger.info("Stepwise calculation: T_start=%.2f, T_end=%.2f", t_start, t_end)
    
    temp = np.asarray(temp, dtype=float)
    mass = np.asarray(mass, dtype=float)
    
    idx_start = _find_nearest_index(temp, t_start)
    idx_end = _find_nearest_index(temp, t_end)
    
    if idx_start >= idx_end:
        return MassLossResult(
            delta_y=0.0,
            params={'idx_start': idx_start, 'idx_end': idx_end},
            details="Invalid range: start index >= end index",
            is_valid=False,
            error_message=f"Start index ({idx_start}) >= End index ({idx_end})"
        )
    
    mass_start = mass[idx_start]
    mass_end = mass[idx_end]
    delta_y = mass_start - mass_end
    
    params = {
        'method': 'Stepwise',
        'idx_start': int(idx_start),
        'idx_end': int(idx_end),
        'temp_start_actual': float(temp[idx_start]),
        'temp_end_actual': float(temp[idx_end]),
        'mass_start': float(mass_start),
        'mass_end': float(mass_end),
    }
    
    details = (
        f"Stepwise: Mass({temp[idx_start]:.1f}°C) - Mass({temp[idx_end]:.1f}°C) = "
        f"{mass_start:.3f}% - {mass_end:.3f}% = {delta_y:.3f}%"
    )
    
    logger.info("Stepwise result: ΔY = %.4f%%", delta_y)
    
    return MassLossResult(
        delta_y=float(delta_y),
        params=params,
        details=details,
        is_valid=True
    )


def calc_software(
    temp: np.ndarray,
    mass: np.ndarray,
    t_start: float,
    t_end: float,
    window_pts_left: int = WINDOW_PTS,
    window_pts_right: int = WINDOW_PTS
) -> MassLossResult:
    """
    Calculate mass loss using the Software (parallel tangents) method.
    
    This method approximates the "parallel tangent" approach:
    
    1. Estimate local slopes at T_start and T_end by averaging derivatives in a window
    2. Choose the "flatter" slope (smaller absolute value)
    3. Construct two parallel lines with this slope passing through the TG points
    4. The vertical separation between these parallel lines is the mass loss
    
    Mathematical formulation:
        slope_start = mean(dMass/dT) around idx_start
        slope_end = mean(dMass/dT) around idx_end
        m = slope_start if |slope_start| < |slope_end| else slope_end
        
        Line at start: y = m*T + b1, where b1 = Mass(T_start) - m*T_start
        Line at end:   y = m*T + b2, where b2 = Mass(T_end) - m*T_end
        
        ΔY = |b2 - b1| (constant for all T since lines are parallel)
    
    Args:
        temp: Temperature array in °C
        mass: Mass percentage array
        t_start: Start temperature
        t_end: End temperature
        window_pts_left: Points for slope averaging at start (lower boundary)
        window_pts_right: Points for slope averaging at end (upper boundary)
        
    Returns:
        MassLossResult with computed delta_y and parameters
    """
    logger.info("Software calculation: T_start=%.2f, T_end=%.2f, window_pts_left=%d, window_pts_right=%d", 
               t_start, t_end, window_pts_left, window_pts_right)
    
    temp = np.asarray(temp, dtype=float)
    mass = np.asarray(mass, dtype=float)
    
    idx_start = _find_nearest_index(temp, t_start)
    idx_end = _find_nearest_index(temp, t_end)
    
    if idx_start >= idx_end:
        return MassLossResult(
            delta_y=0.0,
            params={'idx_start': idx_start, 'idx_end': idx_end},
            details="Invalid range: start index >= end index",
            is_valid=False,
            error_message=f"Start index ({idx_start}) >= End index ({idx_end})"
        )
    
    # Compute local slopes
    slope_start = _compute_local_slope(temp, mass, idx_start, window_pts_left)
    slope_end = _compute_local_slope(temp, mass, idx_end, window_pts_right)
    
    # Choose flatter slope
    if abs(slope_start) < abs(slope_end):
        m = slope_start
        slope_chosen = "start"
    else:
        m = slope_end
        slope_chosen = "end"
    
    # Get points
    t_start_actual = temp[idx_start]
    t_end_actual = temp[idx_end]
    mass_start = mass[idx_start]
    mass_end = mass[idx_end]
    
    # Compute intercepts: b = y - m*x
    b1 = mass_start - m * t_start_actual
    b2 = mass_end - m * t_end_actual
    
    # Vertical separation
    delta_y = abs(b2 - b1)
    
    params = {
        'method': 'Software',
        'window_pts_left': window_pts_left,
        'window_pts_right': window_pts_right,
        'idx_start': int(idx_start),
        'idx_end': int(idx_end),
        'temp_start_actual': float(t_start_actual),
        'temp_end_actual': float(t_end_actual),
        'mass_start': float(mass_start),
        'mass_end': float(mass_end),
        'slope_start': float(slope_start),
        'slope_end': float(slope_end),
        'slope_chosen': slope_chosen,
        'm': float(m),
        'b1': float(b1),
        'b2': float(b2),
    }
    
    details = (
        f"Software: slope_start={slope_start:.6f}, slope_end={slope_end:.6f}, "
        f"using {slope_chosen} (m={m:.6f})\n"
        f"b1={b1:.3f}, b2={b2:.3f}, ΔY=|b2-b1|={delta_y:.3f}%"
    )
    
    logger.info("Software result: ΔY = %.4f%%, m = %.6f, slope_chosen = %s", 
               delta_y, m, slope_chosen)
    
    return MassLossResult(
        delta_y=float(delta_y),
        params=params,
        details=details,
        is_valid=True
    )


def calc_tangential_marsh(
    temp: np.ndarray,
    mass: np.ndarray,
    t_start: float,
    t_end: float,
    window_pts_left: int = WINDOW_PTS,
    window_pts_right: int = WINDOW_PTS,
    turning_fraction: float = 0.5
) -> MassLossResult:
    """
    Calculate mass loss using the Tangential/Marsh method.
    
    This method uses two separate tangent lines evaluated at a turning temperature:
    
    1. Compute tangent lines at T_start and T_end using local slopes
    2. Define turning temperature as midpoint: T_turn = (T_start + T_end) / 2
    3. Evaluate both tangent lines at T_turn
    4. Mass loss is the vertical separation at T_turn
    
    Mathematical formulation:
        Tangent at start: y1 = m1*T + b1, m1 = local_slope(T_start), b1 = Mass(T_start) - m1*T_start
        Tangent at end:   y2 = m2*T + b2, m2 = local_slope(T_end), b2 = Mass(T_end) - m2*T_end
        
        T_turn = (T_start + T_end) / 2
        
        y1_at_turn = m1*T_turn + b1
        y2_at_turn = m2*T_turn + b2
        
        ΔY = |y1_at_turn - y2_at_turn|
    
    Args:
        temp: Temperature array in °C
        mass: Mass percentage array
        t_start: Start temperature
        t_end: End temperature
        window_pts_left: Points for slope averaging at start (lower boundary)
        window_pts_right: Points for slope averaging at end (upper boundary)
        turning_fraction: Fraction along range for turning temperature (0-1)
        
    Returns:
        MassLossResult with computed delta_y and parameters
    """
    logger.info("Tangential-Marsh calculation: T_start=%.2f, T_end=%.2f, window_pts_left=%d, window_pts_right=%d", 
               t_start, t_end, window_pts_left, window_pts_right)
    
    temp = np.asarray(temp, dtype=float)
    mass = np.asarray(mass, dtype=float)
    
    idx_start = _find_nearest_index(temp, t_start)
    idx_end = _find_nearest_index(temp, t_end)
    
    if idx_start >= idx_end:
        return MassLossResult(
            delta_y=0.0,
            params={'idx_start': idx_start, 'idx_end': idx_end},
            details="Invalid range: start index >= end index",
            is_valid=False,
            error_message=f"Start index ({idx_start}) >= End index ({idx_end})"
        )
    
    # Compute local slopes
    m1 = _compute_local_slope(temp, mass, idx_start, window_pts_left)
    m2 = _compute_local_slope(temp, mass, idx_end, window_pts_right)
    
    # Get actual values
    t_start_actual = temp[idx_start]
    t_end_actual = temp[idx_end]
    mass_start = mass[idx_start]
    mass_end = mass[idx_end]
    
    # Compute intercepts
    b1 = mass_start - m1 * t_start_actual
    b2 = mass_end - m2 * t_end_actual
    
    # Turning temperature (fraction between start and end)
    turning_fraction = float(turning_fraction)
    turning_fraction = max(0.0, min(1.0, turning_fraction))
    turning_temp = t_start_actual + (t_end_actual - t_start_actual) * turning_fraction
    
    # Evaluate tangents at turning temperature
    y1_at_turn = m1 * turning_temp + b1
    y2_at_turn = m2 * turning_temp + b2
    
    # Mass loss
    delta_y = abs(y1_at_turn - y2_at_turn)
    
    params = {
        'method': 'Tangential-Marsh',
        'window_pts_left': window_pts_left,
        'window_pts_right': window_pts_right,
        'idx_start': int(idx_start),
        'idx_end': int(idx_end),
        'temp_start_actual': float(t_start_actual),
        'temp_end_actual': float(t_end_actual),
        'mass_start': float(mass_start),
        'mass_end': float(mass_end),
        'm1': float(m1),
        'm2': float(m2),
        'b1': float(b1),
        'b2': float(b2),
        'turning_temp': float(turning_temp),
        'turning_fraction': float(turning_fraction),
        'y1_at_turn': float(y1_at_turn),
        'y2_at_turn': float(y2_at_turn),
    }
    
    details = (
        f"Tangential-Marsh: T_turn = {turning_temp:.1f}°C\n"
        f"Tangent 1: y = {m1:.6f}*T + {b1:.3f}, y1({turning_temp:.1f}) = {y1_at_turn:.3f}\n"
        f"Tangent 2: y = {m2:.6f}*T + {b2:.3f}, y2({turning_temp:.1f}) = {y2_at_turn:.3f}\n"
        f"ΔY = |y1 - y2| = {delta_y:.3f}%"
    )
    
    logger.info("Tangential-Marsh result: ΔY = %.4f%%, turning_temp = %.2f°C", 
               delta_y, turning_temp)
    
    return MassLossResult(
        delta_y=float(delta_y),
        params=params,
        details=details,
        is_valid=True
    )


def calculate_mass_loss(
    temp: np.ndarray,
    mass: np.ndarray,
    t_start: float,
    t_end: float,
    method: str,
    window_pts_left: int = WINDOW_PTS,
    window_pts_right: int = WINDOW_PTS,
    marsh_turning_fraction: float = 0.5
) -> MassLossResult:
    """
    Calculate mass loss using the specified method.
    
    Args:
        temp: Temperature array in °C
        mass: Mass percentage array
        t_start: Start temperature
        t_end: End temperature
        method: Method name ('Stepwise', 'Software', 'Tangential-Marsh')
        window_pts_left: Points for slope averaging at start (lower boundary)
        window_pts_right: Points for slope averaging at end (upper boundary)
        marsh_turning_fraction: Fraction along range for turning temperature (0-1)
        
    Returns:
        MassLossResult with computed delta_y and parameters
    """
    method_lower = method.lower().replace('-', '').replace('_', '').replace(' ', '')
    
    if method_lower in ('stepwise', 'simple'):
        return calc_stepwise(temp, mass, t_start, t_end)
    elif method_lower in ('software', 'parallel', 'paralleltangent'):
        return calc_software(temp, mass, t_start, t_end, window_pts_left, window_pts_right)
    elif method_lower in ('tangentialmarsh', 'marsh', 'tangential'):
        return calc_tangential_marsh(temp, mass, t_start, t_end, window_pts_left, window_pts_right, marsh_turning_fraction)
    else:
        return MassLossResult(
            delta_y=0.0,
            params={},
            details=f"Unknown method: {method}",
            is_valid=False,
            error_message=f"Unknown calculation method: {method}"
        )
