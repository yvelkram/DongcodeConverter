import logging

import pipeline_a.area_calculator as area_calculator
import pipeline_a.geojson_loader as geojson_loader
import config

logger = logging.getLogger(__name__)


def classify_changes(code_map_before, code_map_after):
    """Classify change types between two code maps and produce mapping records.

    Compares before/after versions of code geometries and assigns each
    code a change type: PASS, SPLIT, MERGE, COMPLEX, or WARN.

    Handles two kinds of SPLIT:
      (A) Code-replacement SPLIT: code_from disappears in after, two or more
          new codes appear and cover its geometry.
      (B) Persistent-code SPLIT: code_from exists in both versions but its
          geometry shrinks because a new code (only_after) carves out part
          of its former territory.  The retained record and the carved-out
          record are both classified as SPLIT.

    Args:
        code_map_before: dict -- {code (str): geometry_dict} for the before version.
        code_map_after:  dict -- {code (str): geometry_dict} for the after version.

    Returns:
        list[dict]: Mapping records. Each dict contains:
            - code_from   (str)
            - code_to     (str)
            - change_type (str)
            - weight      (float)
            - warn_flag   (int)
    """
    records = []

    # Step 1. Extract code sets
    codes_before = set(code_map_before.keys())
    codes_after  = set(code_map_after.keys())

    # Step 2. Set operations
    unchanged    = codes_before & codes_after
    only_before  = codes_before - codes_after
    only_after   = codes_after  - codes_before

    # Validate code format for all before codes -- invalid ones become WARN
    invalid_codes = set()
    for code in codes_before:
        if not geojson_loader.validate_code_format(code):
            logger.warning("Invalid code format detected, marking as WARN: %s", code)
            invalid_codes.add(code)

    # Step 3a. Detect persistent-code SPLITs (type B):
    #   For each only_after code, check if its geometry significantly overlaps
    #   with any unchanged code's before-geometry.  If so, that unchanged code
    #   is reclassified from PASS to SPLIT.
    #
    # persistent_split_map: {code_from (unchanged) -> [code_to (only_after), ...]}
    persistent_split_map = {}

    if only_after:
        for code_to in only_after:
            geom_to   = code_map_after[code_to]
            area_to   = area_calculator.calc_area(geom_to)
            if area_to <= 0.0:
                continue
            for code_from in unchanged:
                if code_from in invalid_codes:
                    continue
                geom_from  = code_map_before[code_from]
                area_from  = area_calculator.calc_area(geom_from)
                if area_from <= 0.0:
                    continue
                inter_area = area_calculator.calc_intersection_area(geom_from, geom_to)
                # Use ratio relative to before-geometry to decide significance
                ratio = inter_area / area_from
                if ratio >= config.AREA_OVERLAP_THRESH:
                    if code_from not in persistent_split_map:
                        persistent_split_map[code_from] = []
                    persistent_split_map[code_from].append(code_to)

    # Step 3b. Classify unchanged codes as PASS or persistent SPLIT
    for code in unchanged:
        if code in invalid_codes:
            records.append({
                "code_from":   code,
                "code_to":     "",
                "change_type": config.CHANGE_TYPE_WARN,
                "weight":      0.0,
                "warn_flag":   1,
            })
        elif code in persistent_split_map:
            # Type-B SPLIT: code persists but geometry was partially carved out
            geom_before = code_map_before[code]
            geom_after  = code_map_after[code]
            area_before = area_calculator.calc_area(geom_before)

            # Retained portion weight (code -> same code)
            area_retained = area_calculator.calc_area(geom_after)
            w_self = round(area_retained / area_before, config.WEIGHT_PRECISION) if area_before > 0 else 0.0

            records.append({
                "code_from":   code,
                "code_to":     code,
                "change_type": config.CHANGE_TYPE_SPLIT,
                "weight":      w_self,
                "warn_flag":   0,
            })

            # Carved-out portion weights (code -> each new code_to)
            for code_to in persistent_split_map[code]:
                geom_to    = code_map_after[code_to]
                inter_area = area_calculator.calc_intersection_area(geom_before, geom_to)
                w_to = round(inter_area / area_before, config.WEIGHT_PRECISION) if area_before > 0 else 0.0
                records.append({
                    "code_from":   code,
                    "code_to":     code_to,
                    "change_type": config.CHANGE_TYPE_SPLIT,
                    "weight":      w_to,
                    "warn_flag":   0,
                })
        else:
            records.append({
                "code_from":   code,
                "code_to":     code,
                "change_type": config.CHANGE_TYPE_PASS,
                "weight":      1.0,
                "warn_flag":   0,
            })

    # Codes in only_before that are already invalid -> WARN immediately
    warn_only_before  = only_before & invalid_codes
    valid_only_before = only_before - invalid_codes

    for code in warn_only_before:
        records.append({
            "code_from":   code,
            "code_to":     "",
            "change_type": config.CHANGE_TYPE_WARN,
            "weight":      0.0,
            "warn_flag":   1,
        })

    # Collect only_after codes that were already handled by persistent-split logic
    handled_only_after = set()
    for code_to_list in persistent_split_map.values():
        for code_to in code_to_list:
            handled_only_after.add(code_to)

    # Remaining only_after codes (not handled by persistent-split) are
    # candidates for type-A SPLIT, MERGE, COMPLEX, or WARN detection.
    remaining_only_after = only_after - handled_only_after

    # Step 4. Candidate pair discovery for valid only_before codes
    # Only pair against remaining_only_after codes (not yet handled).
    candidate_pairs = []
    for code_from in valid_only_before:
        geom_from = code_map_before[code_from]
        for code_to in remaining_only_after:
            geom_to    = code_map_after[code_to]
            inter_area = area_calculator.calc_intersection_area(geom_from, geom_to)
            area_from  = area_calculator.calc_area(geom_from)
            if area_from > 0.0:
                ratio = inter_area / area_from
            else:
                ratio = 0.0
            if ratio >= config.AREA_OVERLAP_THRESH:
                candidate_pairs.append((code_from, code_to))

    # Step 5. Batch weight calculation for all candidate pairs
    weight_map = {}
    if candidate_pairs:
        weight_map = area_calculator.calc_intersection_weights(
            code_map_before,
            code_map_after,
            candidate_pairs,
        )

    # Step 6. Build adjacency structures
    from_to_map = {code: [] for code in valid_only_before}
    to_from_map = {code: [] for code in remaining_only_after}

    for (code_from, code_to), weight in weight_map.items():
        if weight > 0.0:
            from_to_map[code_from].append(code_to)
            if code_to in to_from_map:
                to_from_map[code_to].append(code_from)

    # Collect codes already handled (COMPLEX/MERGE/SPLIT) to avoid double-processing
    handled_from = set()

    # Step 6-7. Classify and generate records (type-A splits)
    for code_from in valid_only_before:
        if code_from in handled_from:
            continue

        matched_to = from_to_map.get(code_from, [])

        # No intersection at all -> WARN
        if not matched_to:
            records.append({
                "code_from":   code_from,
                "code_to":     "",
                "change_type": config.CHANGE_TYPE_WARN,
                "weight":      0.0,
                "warn_flag":   1,
            })
            handled_from.add(code_from)
            continue

        # Expand connected component to determine classification
        group_from = set()
        group_to   = set()
        queue = [code_from]
        while queue:
            cf = queue.pop()
            if cf in group_from:
                continue
            group_from.add(cf)
            for ct in from_to_map.get(cf, []):
                if ct not in group_to:
                    group_to.add(ct)
                    for cf2 in to_from_map.get(ct, []):
                        if cf2 not in group_from:
                            queue.append(cf2)

        n_from = len(group_from)
        n_to   = len(group_to)

        if n_from > 1 and n_to > 1:
            # COMPLEX: N:M relationship
            for cf in group_from:
                for ct in from_to_map.get(cf, []):
                    records.append({
                        "code_from":   cf,
                        "code_to":     ct,
                        "change_type": config.CHANGE_TYPE_COMPLEX,
                        "weight":      -1,
                        "warn_flag":   1,
                    })
                handled_from.add(cf)

        elif n_from == 1 and n_to > 1:
            # SPLIT: 1 before -> N after (type A)
            for ct in group_to:
                w = weight_map.get((code_from, ct), 0.0)
                records.append({
                    "code_from":   code_from,
                    "code_to":     ct,
                    "change_type": config.CHANGE_TYPE_SPLIT,
                    "weight":      w,
                    "warn_flag":   0,
                })
            handled_from.add(code_from)

        elif n_from > 1 and n_to == 1:
            # MERGE: N before -> 1 after
            ct = next(iter(group_to))
            for cf in group_from:
                records.append({
                    "code_from":   cf,
                    "code_to":     ct,
                    "change_type": config.CHANGE_TYPE_MERGE,
                    "weight":      1.0,
                    "warn_flag":   0,
                })
                handled_from.add(cf)

        else:
            # 1:1 match -- check PASS threshold
            ct = next(iter(group_to))
            w  = weight_map.get((code_from, ct), 0.0)
            if w >= config.PASS_OVERLAP_THRESH:
                records.append({
                    "code_from":   code_from,
                    "code_to":     ct,
                    "change_type": config.CHANGE_TYPE_PASS,
                    "weight":      1.0,
                    "warn_flag":   0,
                })
            else:
                records.append({
                    "code_from":   code_from,
                    "code_to":     "",
                    "change_type": config.CHANGE_TYPE_WARN,
                    "weight":      0.0,
                    "warn_flag":   1,
                })
            handled_from.add(code_from)

    return records
