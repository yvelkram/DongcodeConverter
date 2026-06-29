import os
import pathlib

# Base directory: dong_converter/ package root
BASE_DIR = pathlib.Path(__file__).parent

# Directory paths
REFERENCE_DIR    = BASE_DIR / "reference"
TRANSITIONS_DIR  = REFERENCE_DIR / "transitions"
GEOJSON_DIR      = REFERENCE_DIR / "geojson"
VERSION_REGISTRY = REFERENCE_DIR / "version_registry.csv"

# Pipeline A defaults
ADM_CODE_FIELD      = "adm_cd2"
AREA_OVERLAP_THRESH = 0.01
PASS_OVERLAP_THRESH = 0.99
WEIGHT_PRECISION    = 6

# Change type labels
CHANGE_TYPE_PASS    = "PASS"
CHANGE_TYPE_SPLIT   = "SPLIT"
CHANGE_TYPE_MERGE   = "MERGE"
CHANGE_TYPE_COMPLEX = "COMPLEX"
CHANGE_TYPE_WARN    = "WARN"

# Output CSV column order
TRANSITION_CSV_COLUMNS = ["code_from", "code_to", "change_type", "weight", "warn_flag"]

# Pipeline B defaults
DEFAULT_NUMERIC_AGG = "sum"        # numeric column aggregation: sum / weighted_mean
DEFAULT_STRING_AGG  = "first"      # string column aggregation: concat / first / na

CONVERSION_LOG_COLUMNS = [
    "row_index", "code_from", "code_to", "change_type",
    "method", "weight", "status",
]

# Column aliases (absorb column-name differences across versions)
COLUMN_ALIASES = {
    "adm_cd": "adm_cd2",  # 8-digit legacy code -> 10-digit standard field
}

# Error handling
HALT_ON_ERROR = True  # BETA: halt immediately on ERROR
