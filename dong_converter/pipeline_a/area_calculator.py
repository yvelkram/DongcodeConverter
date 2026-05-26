import shapely.geometry
import config


def calc_area(geometry):
    """Return the area of a GeoJSON geometry dict (Polygon or MultiPolygon).

    The area is in the native coordinate unit (degrees squared).
    Projection transformation is intentionally omitted because only
    the ratio between areas (weight) is meaningful, not absolute values.

    Args:
        geometry: dict -- GeoJSON geometry dictionary.

    Returns:
        float: Area of the polygon.

    Raises:
        ValueError: If the geometry cannot be converted to a shapely object.
    """
    try:
        shape = shapely.geometry.shape(geometry)
    except Exception as e:
        raise ValueError("Failed to convert geometry to shapely shape: %s" % e)
    return shape.area


def calc_intersection_area(geom_a, geom_b):
    """Return the intersection area of two GeoJSON geometry dicts.

    Args:
        geom_a: dict -- GeoJSON geometry dictionary (before version).
        geom_b: dict -- GeoJSON geometry dictionary (after version).

    Returns:
        float: Intersection area. Returns 0.0 if there is no intersection.
    """
    shape_a = shapely.geometry.shape(geom_a)
    shape_b = shapely.geometry.shape(geom_b)
    intersection = shape_a.intersection(shape_b)
    return intersection.area


def calc_intersection_weights(geom_before_map, geom_after_map, candidate_pairs):
    """Calculate weight for each candidate (code_from, code_to) pair.

    Weight is defined as:
        intersection_area(code_from, code_to) / area(code_from)

    Weights below config.AREA_OVERLAP_THRESH are set to 0.0.
    Weights are rounded to config.WEIGHT_PRECISION decimal places.

    Args:
        geom_before_map: dict -- {code: geometry_dict} for the before version.
        geom_after_map:  dict -- {code: geometry_dict} for the after version.
        candidate_pairs: list of (code_from, code_to) tuples to evaluate.

    Returns:
        dict: {(code_from, code_to): weight (float)}
    """
    weight_map = {}

    for code_from, code_to in candidate_pairs:
        geom_from = geom_before_map.get(code_from)
        geom_to   = geom_after_map.get(code_to)

        if geom_from is None or geom_to is None:
            weight_map[(code_from, code_to)] = 0.0
            continue

        area_from = calc_area(geom_from)

        # Guard against zero-area polygon to prevent ZeroDivisionError
        if area_from == 0.0:
            weight_map[(code_from, code_to)] = 0.0
            continue

        inter_area = calc_intersection_area(geom_from, geom_to)
        weight = inter_area / area_from

        # Discard negligible overlaps
        if weight < config.AREA_OVERLAP_THRESH:
            weight = 0.0

        weight = round(weight, config.WEIGHT_PRECISION)
        weight_map[(code_from, code_to)] = weight

    return weight_map
