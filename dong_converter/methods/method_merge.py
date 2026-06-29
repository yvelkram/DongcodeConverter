import shapely.geometry as shapely_geometry
import shapely.ops as shapely_ops
import config


def _classify_numeric(value):
    """Classify a property value as numeric or string-like.

    Numeric classification is based purely on float/int convertibility,
    not on the original Python type.

    Args:
        value: original property value.

    Returns:
        tuple: (is_numeric (bool), numeric_value (int|float|None)).
            numeric_value is None when is_numeric is False.
    """
    if isinstance(value, bool):
        return False, None

    if isinstance(value, (int, float)):
        return True, value

    if isinstance(value, str):
        try:
            return True, int(value)
        except ValueError:
            pass
        try:
            return True, float(value)
        except ValueError:
            pass

    return False, None


def apply_merge(features, code_to, numeric_agg, string_agg):
    """Apply a MERGE-type method to N Features with different code_from.

    Args:
        features: list[dict] -- N source Features to merge.
        code_to: str -- merged administrative code.
        numeric_agg: str -- numeric column aggregation mode.
        string_agg: str -- string column aggregation mode
            ("concat" / "first" / "na").

    Returns:
        dict: a single merged Feature.

    Raises:
        ValueError: If features is empty.
        NotImplementedError: If numeric_agg == "weighted_mean" (ALPHA stage).
    """
    if not features:
        raise ValueError("apply_merge() requires at least one feature.")

    if numeric_agg == "weighted_mean":
        raise NotImplementedError(
            "numeric_agg='weighted_mean' is not implemented in BETA stage."
        )

    # Collect the union of property column names, preserving first-seen order.
    all_columns = []
    for feature in features:
        for column in feature.get("properties", {}):
            if column not in all_columns:
                all_columns.append(column)

    merged_properties = {}

    for column in all_columns:
        values = [feature.get("properties", {}).get(column) for feature in features]
        classified = [_classify_numeric(value) for value in values]

        if all(is_numeric for is_numeric, _ in classified):
            numeric_values = [numeric_value for _, numeric_value in classified]
            # numeric_agg == "sum": sum all N values.
            merged_properties[column] = sum(numeric_values)
        else:
            if string_agg == "concat":
                merged_properties[column] = "/".join(str(value) for value in values)
            elif string_agg == "na":
                merged_properties[column] = None
            else:
                # string_agg == "first" (default fallback as well)
                merged_properties[column] = values[0]

    merged_properties[config.ADM_CODE_FIELD] = code_to

    shapes = [shapely_geometry.shape(feature["geometry"]) for feature in features]
    merged_shape = shapely_ops.unary_union(shapes)
    merged_geometry = shapely_geometry.mapping(merged_shape)

    return {
        "type": "Feature",
        "properties": merged_properties,
        "geometry": merged_geometry,
    }
