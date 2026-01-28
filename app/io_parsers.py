"""
I/O Parsers for the TGA Analysis application.

Provides:
- NETZSCH-like file parser (primary)
- Generic CSV parser (fallback)
- Column mapping dialog for unrecognized formats
"""

import csv
import io
import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt

from app.models import CurveData, ParseMetadata
from app.logging_setup import get_logger

logger = get_logger('io_parsers')


# Canonical column names
COL_TEMP = 'Temp_C'
COL_TIME = 'Time_min'
COL_MASS = 'Mass_pct'

# NETZSCH parsing constants
NETZSCH_ENCODING = 'ISO-8859-1'
NETZSCH_HEADER_LINES = 34
NETZSCH_SEP = ';'
NETZSCH_DECIMAL = ','
NETZSCH_FILETYPE_LINE = 3  # 0-indexed

# Temperature column variants commonly found in NETZSCH exports
TEMP_COLUMN_VARIANTS = [
    "Temp./°C",
    "Temp./Â°C",  # Encoding artifact
    "Temp./°C",
    "Temp./C",
    "Temperature/°C",
    "Temperature/Â°C",
    "Temperatur/°C",
]

# Time column variants
TIME_COLUMN_VARIANTS = [
    "Time/min",
    "Zeit/min",
    "t/min",
]

# Mass column variants
MASS_COLUMN_VARIANTS = [
    "Mass/%",
    "TG/%",
    "Masse/%",
    "Mass/mg",  # Will need conversion if mg
]

# Minimum temperature threshold
MIN_TEMP_THRESHOLD = 40.0


class ColumnMappingDialog(QDialog):
    """
    Dialog for manually mapping columns when automatic detection fails.
    """
    
    def __init__(self, columns: List[str], sample_data: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.sample_data = sample_data
        self.mapping = {}
        self._init_ui()
        
    def _init_ui(self):
        self.setWindowTitle("Column Mapping")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Could not automatically detect required columns.\n"
            "Please map the columns from your file to the required fields.\n"
            "Required: Temperature (°C), Time (min), Mass (%)"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Preview table
        preview_group = QGroupBox("Data Preview (first 5 rows)")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_table = QTableWidget()
        self.preview_table.setRowCount(min(5, len(self.sample_data)))
        self.preview_table.setColumnCount(len(self.columns))
        self.preview_table.setHorizontalHeaderLabels(self.columns)
        
        for i in range(min(5, len(self.sample_data))):
            for j, col in enumerate(self.columns):
                item = QTableWidgetItem(str(self.sample_data.iloc[i][col]))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.preview_table.setItem(i, j, item)
        
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)
        
        # Mapping controls
        mapping_group = QGroupBox("Column Mapping")
        mapping_layout = QFormLayout(mapping_group)
        
        none_option = ["(None)"] + self.columns
        
        self.temp_combo = QComboBox()
        self.temp_combo.addItems(none_option)
        self._auto_select_combo(self.temp_combo, ['temp', 'temperature', 'temperatur'], ['c', '°c'])
        mapping_layout.addRow("Temperature (°C):", self.temp_combo)
        
        self.time_combo = QComboBox()
        self.time_combo.addItems(none_option)
        self._auto_select_combo(self.time_combo, ['time', 'zeit', 't/'], ['min'])
        mapping_layout.addRow("Time (min):", self.time_combo)
        
        self.mass_combo = QComboBox()
        self.mass_combo.addItems(none_option)
        self._auto_select_combo(self.mass_combo, ['mass', 'tg', 'masse', 'weight'], ['%', 'pct'])
        mapping_layout.addRow("Mass (%):", self.mass_combo)
        
        layout.addWidget(mapping_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self._on_ok)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
    
    def _auto_select_combo(self, combo: QComboBox, keywords: List[str], units: List[str]):
        """Try to auto-select a column based on keywords and units."""
        for i, col in enumerate(self.columns):
            col_lower = col.lower()
            has_keyword = any(kw in col_lower for kw in keywords)
            has_unit = any(u in col_lower for u in units) if units else True
            if has_keyword and has_unit:
                combo.setCurrentIndex(i + 1)  # +1 for "(None)" option
                break
    
    def _on_ok(self):
        """Validate and accept the mapping."""
        temp_col = self.temp_combo.currentText()
        time_col = self.time_combo.currentText()
        mass_col = self.mass_combo.currentText()
        
        if temp_col == "(None)" or time_col == "(None)" or mass_col == "(None)":
            QMessageBox.warning(
                self, "Incomplete Mapping",
                "All three columns (Temperature, Time, Mass) must be mapped."
            )
            return
        
        if len({temp_col, time_col, mass_col}) != 3:
            QMessageBox.warning(
                self, "Duplicate Mapping",
                "Each column can only be mapped to one field."
            )
            return
        
        self.mapping = {
            temp_col: COL_TEMP,
            time_col: COL_TIME,
            mass_col: COL_MASS,
        }
        self.accept()
    
    def get_mapping(self) -> Dict[str, str]:
        """Get the column mapping."""
        return self.mapping


def _clean_column_name(col: str) -> str:
    """Clean a column name by stripping whitespace and leading #."""
    col = str(col).strip()
    if col.startswith('#'):
        col = col[1:].strip()
    return col


def _find_column(df: pd.DataFrame, variants: List[str], contains_keywords: List[str] = None) -> Optional[str]:
    """
    Find a column matching given variants or keywords.
    
    Args:
        df: DataFrame to search
        variants: List of exact column names to try
        contains_keywords: List of keywords to search for (case-insensitive)
        
    Returns:
        Column name if found, None otherwise
    """
    columns = [_clean_column_name(c) for c in df.columns]
    original_cols = list(df.columns)
    
    # Try exact matches first
    for variant in variants:
        for i, col in enumerate(columns):
            if col == variant or col == _clean_column_name(variant):
                return original_cols[i]
    
    # Try case-insensitive contains
    if contains_keywords:
        for i, col in enumerate(columns):
            col_lower = col.lower()
            if all(kw.lower() in col_lower for kw in contains_keywords):
                return original_cols[i]
    
    return None


def parse_netzsch(filepath: str) -> Tuple[Optional[CurveData], List[str]]:
    """
    Parse a NETZSCH-like TGA export file.
    
    NETZSCH files have:
    - Encoding: ISO-8859-1
    - Header: 34 lines before data
    - Separator: semicolon
    - Decimal: comma
    - FileType on line 4 (index 3)
    
    Args:
        filepath: Path to the file
        
    Returns:
        Tuple of (CurveData or None, list of warnings)
    """
    warnings = []
    logger.info("Parsing NETZSCH file: %s", filepath)
    
    try:
        # Read entire file
        with open(filepath, 'r', encoding=NETZSCH_ENCODING, errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < NETZSCH_HEADER_LINES + 1:
            raise ValueError(f"File too short: {len(lines)} lines (expected at least {NETZSCH_HEADER_LINES + 1})")
        
        # Extract filetype from line 4
        filetype = lines[NETZSCH_FILETYPE_LINE].strip() if len(lines) > NETZSCH_FILETYPE_LINE else "Unknown"
        logger.info("Detected filetype: %s", filetype)
        
        # Join data lines and parse with pandas
        data_text = ''.join(lines[NETZSCH_HEADER_LINES:])
        
        df = pd.read_csv(
            io.StringIO(data_text),
            sep=NETZSCH_SEP,
            decimal=NETZSCH_DECIMAL,
            encoding=NETZSCH_ENCODING,
            on_bad_lines='skip'
        )
        
        # Clean column names
        df.columns = [_clean_column_name(c) for c in df.columns]
        original_columns = list(df.columns)
        logger.debug("Columns found: %s", original_columns)
        
        # Find temperature column
        temp_col = _find_column(df, TEMP_COLUMN_VARIANTS, ['temp', 'c'])
        if temp_col is None:
            raise ValueError("Could not find temperature column")
        
        # Find time column
        time_col = _find_column(df, TIME_COLUMN_VARIANTS, ['time', 'min'])
        if time_col is None:
            time_col = _find_column(df, TIME_COLUMN_VARIANTS, ['zeit', 'min'])
        if time_col is None:
            raise ValueError("Could not find time column")
        
        # Find mass column
        mass_col = _find_column(df, MASS_COLUMN_VARIANTS, ['mass', '%'])
        if mass_col is None:
            mass_col = _find_column(df, MASS_COLUMN_VARIANTS, ['tg', '%'])
        if mass_col is None:
            raise ValueError("Could not find mass column")
        
        logger.info("Column mapping: Temp=%s, Time=%s, Mass=%s", temp_col, time_col, mass_col)
        
        # Rename to canonical names
        df = df.rename(columns={
            temp_col: COL_TEMP,
            time_col: COL_TIME,
            mass_col: COL_MASS,
        })
        
        # Keep only required columns
        df = df[[COL_TEMP, COL_TIME, COL_MASS]].copy()
        
        # Convert to numeric
        for col in [COL_TEMP, COL_TIME, COL_MASS]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop rows with NaN in required columns
        initial_rows = len(df)
        df = df.dropna(subset=[COL_TEMP, COL_TIME, COL_MASS])
        dropped_rows = initial_rows - len(df)
        if dropped_rows > 0:
            warnings.append(f"Dropped {dropped_rows} rows with missing/invalid values")
            logger.warning("Dropped %d rows with missing/invalid values", dropped_rows)
        
        # Filter temperature >= 40
        df = df[df[COL_TEMP] >= MIN_TEMP_THRESHOLD].copy()
        if len(df) == 0:
            raise ValueError(f"No data remaining after filtering Temp >= {MIN_TEMP_THRESHOLD}°C")
        
        # Reset index
        df = df.reset_index(drop=True)
        
        logger.info("Successfully parsed %d data points", len(df))
        
        # Create metadata
        metadata = ParseMetadata(
            filetype=filetype,
            encoding=NETZSCH_ENCODING,
            separator=NETZSCH_SEP,
            decimal=NETZSCH_DECIMAL,
            header_lines_skipped=NETZSCH_HEADER_LINES,
            original_columns=original_columns,
            header_lines=[line.rstrip('\n') for line in lines[:NETZSCH_HEADER_LINES]],
        )
        
        # Create CurveData
        curve = CurveData(
            path=filepath,
            name=os.path.basename(filepath),
            raw_df=df,
            parse_metadata=metadata,
            parse_warnings=warnings,
        )
        
        return curve, warnings
        
    except Exception as e:
        logger.error("NETZSCH parsing failed: %s", str(e), exc_info=True)
        return None, [f"NETZSCH parsing failed: {str(e)}"]


def parse_generic_csv(filepath: str, column_mapping: Dict[str, str] = None) -> Tuple[Optional[CurveData], List[str]]:
    """
    Parse a generic CSV/TSV file.
    
    Attempts to auto-detect delimiter and decimal separator.
    If column_mapping is not provided and columns can't be auto-detected,
    returns None (caller should show mapping dialog).
    
    Args:
        filepath: Path to the file
        column_mapping: Optional dict mapping file columns to canonical names
        
    Returns:
        Tuple of (CurveData or None, list of warnings)
    """
    warnings = []
    logger.info("Parsing generic CSV: %s", filepath)
    
    try:
        # Try to sniff the dialect
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            sample = f.read(8192)
        
        # Detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample, delimiters=',;\t')
            delimiter = dialect.delimiter
        except csv.Error:
            # Default to comma
            delimiter = ','
        
        logger.debug("Detected delimiter: %r", delimiter)
        
        # Try different decimal separators
        for decimal in ['.', ',']:
            try:
                df = pd.read_csv(
                    filepath,
                    sep=delimiter,
                    decimal=decimal,
                    encoding='utf-8',
                    on_bad_lines='skip'
                )
                
                # Check if we got numeric data
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) >= 3:
                    break
            except Exception:
                continue
        else:
            raise ValueError("Could not parse file with any delimiter/decimal combination")
        
        # Clean column names
        df.columns = [_clean_column_name(c) for c in df.columns]
        original_columns = list(df.columns)
        
        # Apply or detect column mapping
        if column_mapping:
            # Use provided mapping
            df = df.rename(columns=column_mapping)
        else:
            # Try to auto-detect columns
            temp_col = _find_column(df, TEMP_COLUMN_VARIANTS, ['temp', 'c'])
            time_col = _find_column(df, TIME_COLUMN_VARIANTS, ['time', 'min'])
            mass_col = _find_column(df, MASS_COLUMN_VARIANTS, ['mass', '%'])
            
            if temp_col is None or time_col is None or mass_col is None:
                # Can't auto-detect, need mapping dialog
                return None, ["Could not auto-detect columns. Manual mapping required."]
            
            df = df.rename(columns={
                temp_col: COL_TEMP,
                time_col: COL_TIME,
                mass_col: COL_MASS,
            })
        
        # Keep only required columns
        if not all(col in df.columns for col in [COL_TEMP, COL_TIME, COL_MASS]):
            return None, ["Required columns not found after mapping"]
        
        df = df[[COL_TEMP, COL_TIME, COL_MASS]].copy()
        
        # Convert to numeric
        for col in [COL_TEMP, COL_TIME, COL_MASS]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop NaN rows
        initial_rows = len(df)
        df = df.dropna(subset=[COL_TEMP, COL_TIME, COL_MASS])
        dropped_rows = initial_rows - len(df)
        if dropped_rows > 0:
            warnings.append(f"Dropped {dropped_rows} rows with missing/invalid values")
        
        # Filter temperature
        df = df[df[COL_TEMP] >= MIN_TEMP_THRESHOLD].copy()
        if len(df) == 0:
            raise ValueError(f"No data remaining after filtering Temp >= {MIN_TEMP_THRESHOLD}°C")
        
        df = df.reset_index(drop=True)
        
        logger.info("Successfully parsed %d data points", len(df))
        
        # Capture header lines for display
        header_lines: List[str] = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for _ in range(50):
                    line = f.readline()
                    if not line:
                        break
                    header_lines.append(line.rstrip('\n'))
        except Exception:
            header_lines = []

        metadata = ParseMetadata(
            filetype="Generic CSV",
            encoding='utf-8',
            separator=delimiter,
            decimal=decimal,
            header_lines_skipped=0,
            original_columns=original_columns,
            header_lines=header_lines,
        )
        
        curve = CurveData(
            path=filepath,
            name=os.path.basename(filepath),
            raw_df=df,
            parse_metadata=metadata,
            parse_warnings=warnings,
        )
        
        return curve, warnings
        
    except Exception as e:
        logger.error("Generic CSV parsing failed: %s", str(e), exc_info=True)
        return None, [f"Generic CSV parsing failed: {str(e)}"]


def load_tga_file(filepath: str, parent_widget=None) -> Tuple[Optional[CurveData], List[str]]:
    """
    Load a TGA file, trying NETZSCH parser first, then falling back to generic.
    
    Args:
        filepath: Path to the file
        parent_widget: Parent widget for dialogs
        
    Returns:
        Tuple of (CurveData or None, list of warnings)
    """
    logger.info("Loading TGA file: %s", filepath)
    all_warnings = []
    
    # Try NETZSCH parser first
    curve, warnings = parse_netzsch(filepath)
    all_warnings.extend(warnings)
    
    if curve is not None:
        logger.info("Successfully loaded with NETZSCH parser")
        return curve, all_warnings
    
    # Try generic parser
    curve, warnings = parse_generic_csv(filepath)
    all_warnings.extend(warnings)
    
    if curve is not None:
        logger.info("Successfully loaded with generic CSV parser")
        return curve, all_warnings
    
    # Need column mapping dialog
    if parent_widget is not None:
        logger.info("Showing column mapping dialog")
        
        # Read file for preview
        try:
            df = pd.read_csv(filepath, nrows=10, encoding='utf-8', on_bad_lines='skip')
            df.columns = [_clean_column_name(c) for c in df.columns]
            
            dialog = ColumnMappingDialog(list(df.columns), df, parent_widget)
            if dialog.exec_() == QDialog.Accepted:
                mapping = dialog.get_mapping()
                curve, warnings = parse_generic_csv(filepath, mapping)
                all_warnings.extend(warnings)
                
                if curve is not None:
                    logger.info("Successfully loaded with manual column mapping")
                    return curve, all_warnings
        except Exception as e:
            all_warnings.append(f"Column mapping failed: {str(e)}")
    
    logger.error("Failed to load file: %s", filepath)
    return None, all_warnings


def get_sample_dataframe(filepath: str, nrows: int = 10) -> Optional[pd.DataFrame]:
    """
    Get a sample DataFrame from a file for preview.
    
    Args:
        filepath: Path to the file
        nrows: Number of rows to read
        
    Returns:
        DataFrame or None if failed
    """
    try:
        # Try NETZSCH format first
        with open(filepath, 'r', encoding=NETZSCH_ENCODING, errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) > NETZSCH_HEADER_LINES:
            data_text = ''.join(lines[NETZSCH_HEADER_LINES:NETZSCH_HEADER_LINES + nrows + 1])
            df = pd.read_csv(
                io.StringIO(data_text),
                sep=NETZSCH_SEP,
                decimal=NETZSCH_DECIMAL,
                nrows=nrows,
            )
            df.columns = [_clean_column_name(c) for c in df.columns]
            return df
    except Exception:
        pass
    
    # Try generic
    try:
        df = pd.read_csv(filepath, nrows=nrows, encoding='utf-8', on_bad_lines='skip')
        df.columns = [_clean_column_name(c) for c in df.columns]
        return df
    except Exception:
        return None
