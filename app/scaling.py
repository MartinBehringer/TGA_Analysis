"""
Adaptive UI scaling for different screen resolutions.

Computes a scale factor based on the primary screen's available geometry
relative to a 1920×1080 reference. All UI pixel values and font sizes
are multiplied by this factor so the application looks consistent on
13-inch laptops and large desktop monitors alike.
"""

import re
from PyQt5.QtWidgets import QApplication, QDesktopWidget


# Reference resolution that the hard-coded pixel values were designed for.
_REF_WIDTH = 1920
_REF_HEIGHT = 1080

# Clamp the factor so the UI never gets unreasonably large or tiny.
_MIN_FACTOR = 0.55
_MAX_FACTOR = 1.6

_scale_factor: float = 1.0


def compute_scale_factor(app: QApplication) -> float:
    """
    Compute and cache a global UI scale factor.

    Uses the *available* height of the primary screen (excludes taskbar)
    compared to the reference height.  Height is the limiting dimension
    on most laptops.
    """
    global _scale_factor

    desktop: QDesktopWidget = app.desktop()
    screen_rect = desktop.availableGeometry(desktop.primaryScreen())

    h_factor = screen_rect.height() / _REF_HEIGHT
    w_factor = screen_rect.width() / _REF_WIDTH
    # Use the smaller axis so nothing overflows
    raw = min(h_factor, w_factor)

    _scale_factor = max(_MIN_FACTOR, min(_MAX_FACTOR, raw))
    return _scale_factor


def sf() -> float:
    """Return the cached scale factor (call compute_scale_factor first)."""
    return _scale_factor


def _recompute_for_screen(screen_rect) -> float:
    """
    Re-compute the scale factor for a specific screen geometry.

    Called when the window is dragged to a different monitor.  Also
    re-applies matplotlib rcParams so plots drawn after this point
    pick up the new sizes.
    """
    global _scale_factor

    h_factor = screen_rect.height() / _REF_HEIGHT
    w_factor = screen_rect.width() / _REF_WIDTH
    raw = min(h_factor, w_factor)

    _scale_factor = max(_MIN_FACTOR, min(_MAX_FACTOR, raw))

    # Update matplotlib rcParams to match
    try:
        from app.styles import apply_matplotlib_style
        apply_matplotlib_style()
    except Exception:
        pass

    return _scale_factor


def scaled(px: int) -> int:
    """Scale an integer pixel value."""
    return max(1, round(px * _scale_factor))


def scaled_f(val: float) -> float:
    """Scale a float value (e.g. figure inches)."""
    return val * _scale_factor


def scaled_font_pt(pt: int) -> int:
    """Scale a font-size in points. Minimum 7 pt for readability."""
    return max(7, round(pt * _scale_factor))


# ---------------------------------------------------------------------------
# Stylesheet post-processing
# ---------------------------------------------------------------------------

def _replace_pt(match: re.Match) -> str:
    """Replace a ``Npt`` font-size token with scaled value."""
    original = int(match.group(1))
    return f"{scaled_font_pt(original)}pt"


def _replace_px(match: re.Match) -> str:
    """Replace a ``Npx`` dimension token with scaled value."""
    original = int(match.group(1))
    return f"{scaled(original)}px"


def scale_stylesheet(css: str) -> str:
    """
    Return *css* with every ``Npt`` and ``Npx`` token proportionally scaled.

    Handles patterns like  ``font-size: 10pt``, ``padding: 6px 10px``,
    ``width: 18px``, ``min-height: 22px``, etc.
    """
    css = re.sub(r'(\d+)pt', _replace_pt, css)
    css = re.sub(r'(\d+)px', _replace_px, css)
    return css
