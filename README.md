# TGA Analysis Tool

A PyQt5-based thermogravimetric analysis (TGA) application optimized for NETZSCH-like exports, with support for generic CSV files.

## Features

- **Multi-curve plotting**: Load and visualize multiple TGA curves simultaneously
- **TG and DTG display**: Toggle visibility of TG (mass) and DTG (derivative) curves independently
- **Flexible X-axis**: Switch between Temperature (°C) and Time (min) modes
- **Smoothing**: Savitzky-Golay smoothing for both TG and DTG with configurable parameters
- **Normalization**: Optional display normalization to 100% at 40°C
- **Mass-loss calculations**: Three methods - Stepwise, Software (parallel tangents), Tangential-Marsh
- **Detail plots**: Visual representation of calculation methods matching computed values
- **Full reproducibility**: JSON export includes all parameters and metadata
- **Operational logging**: Rotating file logs for debugging and audit trails

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. Clone or download this repository

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

```bash
python -m app.main
```

Or run directly:
```bash
python app/main.py
```

## Supported File Formats

### NETZSCH-like Files (Primary)

The application is optimized for NETZSCH TGA export files with the following characteristics:

- **Encoding**: ISO-8859-1
- **Header**: 34 lines before data
- **Separator**: Semicolon (;)
- **Decimal**: Comma (,)
- **Required columns**: Temperature, Time, Mass

Column names are detected automatically using common variants:
- Temperature: `Temp./°C`, `Temperature/°C`, etc.
- Time: `Time/min`, `Zeit/min`, `t/min`
- Mass: `Mass/%`, `TG/%`, `Masse/%`

### Generic CSV Files (Fallback)

If NETZSCH parsing fails, the application attempts generic CSV parsing:

- Auto-detects delimiter (comma, semicolon, tab)
- Auto-detects decimal separator
- If columns cannot be identified automatically, a mapping dialog is shown

## User Interface

### Main Window Layout

```
+-------------------------------------------+-------------+
|                                           |  Controls   |
|         Overview Plot                     |  (Dock)     |
|         (TG/DTG curves)                   |             |
|                                           |             |
+-------------------------------------------+             |
|  Tabs:                                    |             |
|  - Ranges & Results                       |             |
|  - Raw Data                               |             |
|  - Logs                                   |             |
+-------------------------------------------+-------------+
```

### Controls Panel

- **Files**: Open, Remove, Clear buttons
- **Filter**: Search/filter loaded curves
- **Curve List**: Multi-select list with tooltips showing full paths
- **Display Toggles**: Show TG, Show DTG checkboxes
- **X-axis Mode**: Temperature (default) or Time
- **Normalization**: Normalize to 100% at 40°C (display only)
- **DTG Smoothing**: Enable/disable with window and polynomial order
- **TG Smoothing**: Enable/disable with window and polynomial order
- **Overlay Raw**: Show raw data behind smoothed curves

### Tabs

#### Ranges & Results Tab

- **Active Curve**: Select which curve to use for calculations
- **Ranges Table**: Define calculation ranges (Start/End temp, Method, Use Series, Notes)
- **Results Table**: View calculation results (timestamp, curve, method, ΔY, etc.)
- **Detail Plot**: Visual representation of selected calculation

#### Raw Data Tab

- Preview raw data for selected curve
- Option to include derived columns (dtg_raw, dtg_smooth, tg_smooth)

#### Logs Tab

- View recent operational logs
- Refresh and Open Log Folder buttons

## Smoothing

### Savitzky-Golay Filter

Both TG and DTG can be smoothed using the Savitzky-Golay filter from SciPy.

**Parameters:**
- **Window**: Must be odd (enforced by UI). Default: 201
- **Polynomial Order**: Default: 3

**Constraints:**
- Window must be ≤ data length
- Window must be ≥ poly + 2

**Defaults:**
- DTG smoothing: **ON** (window=201, poly=3)
- TG smoothing: **OFF** (window=201, poly=3 when enabled)

## Normalization

Display-only normalization scales TG values so that Mass at 40°C (or nearest point ≥40°C) equals 100%.

**Formula:**
```
scale_factor = 100 / Mass(T=40°C)
Mass_normalized = Mass_raw × scale_factor
```

**Important:**
- Raw data is never modified
- Calculations use the selected series (Raw TG or Smoothed TG)
- Default: OFF

## Mass-Loss Calculation Methods

All methods use TG data (not DTG) with temperature bounds [T_start, T_end].

### Method 1: Stepwise (Simple Difference)

```
ΔY = Mass(T_start) - Mass(T_end)
```

### Method 2: Software (Parallel Tangents)

1. Calculate local slopes at T_start and T_end (averaging over 30 points)
2. Choose the flatter slope (smaller absolute value)
3. Draw two parallel lines through the TG points
4. ΔY = vertical separation between parallel lines

```
m = slope_start if |slope_start| < |slope_end| else slope_end
b1 = Mass(T_start) - m × T_start
b2 = Mass(T_end) - m × T_end
ΔY = |b2 - b1|
```

### Method 3: Tangential-Marsh

1. Calculate tangent lines at both T_start and T_end
2. Define turning temperature: T_turn = (T_start + T_end) / 2
3. Evaluate both tangents at T_turn
4. ΔY = vertical separation at T_turn

```
Tangent 1: y = m1×T + b1  (through T_start)
Tangent 2: y = m2×T + b2  (through T_end)
T_turn = (T_start + T_end) / 2
ΔY = |y1(T_turn) - y2(T_turn)|
```

## Reproducibility

### Calculation Parameters

Each calculation result includes:
- Timestamp
- Curve name and path
- Method used
- Temperature range
- Series used (Raw TG / Smoothed TG)
- All intermediate parameters (slopes, intercepts, window size)
- Smoothing parameters (if applicable)

### Export Formats

**TSV Export:**
- Tab-separated values
- Human-readable
- Suitable for spreadsheet import

**JSON Export:**
- Full reproducibility metadata
- Machine-readable
- Includes all parameters and computed values

Example JSON structure:
```json
{
  "export_timestamp": "2026-01-27T10:30:00",
  "app_version": "1.0.0",
  "results": [
    {
      "timestamp": "2026-01-27T10:25:00",
      "curve_name": "sample1.txt",
      "curve_path": "C:/data/sample1.txt",
      "method": "Software",
      "start_temp": 100.0,
      "end_temp": 200.0,
      "use_series": "Raw TG",
      "delta_y": 5.234,
      "params": {
        "window_pts": 30,
        "slope_start": -0.00123,
        "slope_end": -0.00089,
        "slope_chosen": "end",
        "m": -0.00089,
        "b1": 98.5,
        "b2": 93.266
      },
      "smoothing_params": null
    }
  ]
}
```

## Logging

Logs are stored in `./logs/app.log` with:
- Rotating file handler (2 MB max, 5 backups)
- Format: `timestamp | level | module | message`

Logged events include:
- File load start/end
- Parse warnings and failures
- Calculation actions
- Errors with stack traces

## Project Structure

```
app/
├── __init__.py           # Package init with version info
├── main.py               # Application entry point
├── ui_main_window.py     # QMainWindow layout (UI only)
├── controllers.py        # Signal/slot wiring, no heavy math
├── models.py             # Dataclasses: CurveData, CalcRange, CalcResult, AppState
├── io_parsers.py         # NETZSCH + generic CSV parsers, column mapping dialog
├── processing.py         # Normalization, smoothing, DTG, mass-loss methods
├── plotting.py           # Matplotlib plotting utilities
├── logging_setup.py      # Rotating file handler, log helpers
└── resources/
    └── __init__.py       # Resource path helper
requirements.txt          # Python dependencies
README.md                 # This file
```

## Packaging (Future)

For creating standalone executables, consider:

- **PyInstaller**: `pyinstaller --onefile --windowed app/main.py`
- **cx_Freeze**: Alternative packaging tool
- **Nuitka**: Python compiler for better performance

## Troubleshooting

### Common Issues

1. **File won't load**: Check encoding and delimiter. Try the column mapping dialog.

2. **No data after filtering**: Data is filtered to T ≥ 40°C. Ensure your data includes this range.

3. **Smoothing looks wrong**: Try adjusting window size. Larger windows = more smoothing.

4. **Calculation gives unexpected result**: Check the detail plot to visualize the method. Verify the correct series (Raw/Smoothed) is selected.

### Log Files

Check `./logs/app.log` for detailed error messages and stack traces.

## License

[Specify your license here]

## Contact

[Specify contact information here]
