import json
import logging
import config

logger = logging.getLogger(__name__)


def load_geojson(filepath):
    """Load a GeoJSON file and return its feature list.

    Args:
        filepath: str or pathlib.Path pointing to a GeoJSON file.

    Returns:
        list[dict]: The list of GeoJSON Feature dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON parsing fails or the 'features' key is missing.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as e:
        logger.error(
            "Failed to decode file as UTF-8. File may be EUC-KR or CP949 encoded: %s",
            filepath,
        )
        raise
    except json.JSONDecodeError as e:
        raise ValueError("JSON parsing failed for '%s': %s" % (filepath, e))

    if "features" not in data:
        raise ValueError("'features' key not found in GeoJSON: %s" % filepath)

    return data["features"]


def extract_code_map(features):
    """Extract a mapping of adm_cd2 code to geometry from a feature list.

    Args:
        features: list[dict] returned by load_geojson().

    Returns:
        dict: {adm_cd2 code (str): geometry (dict)}

    Raises:
        ValueError: If a duplicate adm_cd2 code is encountered.
    """
    code_map = {}
    allowed_geometry_types = {"Polygon", "MultiPolygon"}

    for feature in features:
        properties = feature.get("properties", {})
        code = properties.get(config.ADM_CODE_FIELD)
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type") if geometry else None

        # Skip features with unsupported geometry types
        if geom_type not in allowed_geometry_types:
            logger.warning(
                "Skipping feature with unsupported geometry type '%s' (code=%s)",
                geom_type,
                code,
            )
            continue

        # Skip features with missing or empty code
        if code is None or code == "":
            logger.warning("Skipping feature with missing or empty adm_cd2 code.")
            continue

        # Raise on duplicate code
        if code in code_map:
            raise ValueError(
                "Duplicate adm_cd2 code detected: '%s'" % code
            )

        code_map[code] = geometry

    return code_map


def validate_code_format(code):
    """Check whether an adm_cd2 code is a 10-digit numeric string.

    Args:
        code: str to validate.

    Returns:
        bool: True if valid (exactly 10 digits), False otherwise.
    """
    is_valid = isinstance(code, str) and len(code) == 10 and code.isdigit()
    if not is_valid:
        logger.warning("Invalid adm_cd2 code format: '%s'", code)
    return is_valid
