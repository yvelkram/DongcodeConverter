import copy
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


def apply_split(feature, split_targets, numeric_agg, string_agg, target_geometries):
    """Apply a SPLIT-type method to a single Feature.

    Args:
        feature: dict -- original Feature.
        split_targets: list[tuple] -- [(code_to, weight), ...].
        numeric_agg: str -- numeric column aggregation mode.
        string_agg: str -- string column aggregation mode.
        target_geometries: dict -- {code_to: geometry_dict, ...} extracted
            from the target-date reference GeoJSON.

    Returns:
        list[dict]: one Feature per entry in split_targets.

    Raises:
        NotImplementedError: If numeric_agg == "weighted_mean" (ALPHA stage).
        ValueError: If a code_to in split_targets is missing from
            target_geometries.
    """
    if numeric_agg == "weighted_mean":
        raise NotImplementedError(
            "numeric_agg='weighted_mean' is not implemented in BETA stage."
        )

    original_properties = feature.get("properties", {})
    result_features = []

    for code_to, weight in split_targets:
        if code_to not in target_geometries:
            raise ValueError(
                "Target geometry not found for code_to='%s'" % code_to
            )

        new_properties = {}
        for column, value in original_properties.items():
            is_numeric, numeric_value = _classify_numeric(value)
            if is_numeric:
                # numeric_agg == "sum": distribute the original value by weight.
                new_properties[column] = numeric_value * weight
            else:
                # BETA: only string_agg == "first" actually runs; other
                # options are treated the same way (value duplicated as-is).
                new_properties[column] = value

        new_properties[config.ADM_CODE_FIELD] = code_to

        new_feature = copy.deepcopy(feature)
        new_feature["properties"] = new_properties
        new_feature["geometry"] = copy.deepcopy(target_geometries[code_to])
        result_features.append(new_feature)

    return result_features
