import json
import logging
import pathlib

logger = logging.getLogger(__name__)


def write_output(features, output_path, source_metadata):
    """Write a feature list to a GeoJSON FeatureCollection file.

    Args:
        features: list[dict] — Feature list to write.
        output_path: str or pathlib.Path — destination file path.
        source_metadata: dict — e.g. {"crs": {...}}. May be an empty dict.

    Returns:
        str: the absolute path of the saved file.
    """
    output_path = pathlib.Path(output_path)

    feature_collection = {"type": "FeatureCollection", "features": features}

    if "crs" in source_metadata:
        feature_collection["crs"] = source_metadata["crs"]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection, f, ensure_ascii=False)

    absolute_path = str(output_path.resolve())
    logger.debug("Wrote %d features to %s", len(features), absolute_path)

    return absolute_path
