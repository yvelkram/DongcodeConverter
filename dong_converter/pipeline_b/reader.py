import json
import logging
import pipeline_b.normalizer as normalizer
import config

logger = logging.getLogger(__name__)


def read_input(filepath):
    """Read an input GeoJSON file and return a normalized feature list.

    Args:
        filepath: str or pathlib.Path pointing to a GeoJSON file.

    Returns:
        list[dict]: Feature list. Each Feature's "properties" dict has been
            passed through normalizer.normalize_columns().

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON parsing fails, the "features" key is missing, or
            a Feature is missing the config.ADM_CODE_FIELD field.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise
    except UnicodeDecodeError:
        logger.error(
            "Failed to decode file as UTF-8. File may be EUC-KR or CP949 encoded: %s",
            filepath,
        )
        raise
    except json.JSONDecodeError as e:
        raise ValueError("JSON parsing failed for '%s': %s" % (filepath, e))

    if "features" not in data:
        raise ValueError("'features' key not found in GeoJSON: %s" % filepath)

    features = data["features"]
    result = []

    for feature in features:
        properties = feature.get("properties", {})
        normalized_properties = normalizer.normalize_columns(properties)

        if config.ADM_CODE_FIELD not in normalized_properties:
            raise ValueError(
                "Feature missing required field '%s': %s"
                % (config.ADM_CODE_FIELD, normalized_properties)
            )

        new_feature = dict(feature)
        new_feature["properties"] = normalized_properties
        result.append(new_feature)

    return result
