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
