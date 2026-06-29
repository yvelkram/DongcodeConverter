import json
import pathlib
import pipeline_b.reader as reader
import pipeline_b.resolver as resolver
import pipeline_b.writer as writer
import pipeline_b.normalizer as normalizer
import methods.method_recode as method_recode
import methods.method_split as method_split
import methods.method_merge as method_merge
import logger as conv_logger_module
import config


def _resolve_method_config(method_config):
    """Fill missing keys of method_config with config defaults.

    Args:
        method_config: dict|None -- e.g. {"numeric_agg": "sum", "string_agg": "first"}.

    Returns:
        tuple(str, str): (numeric_agg, string_agg).
    """
    method_config = method_config or {}
    numeric_agg = method_config.get("numeric_agg", config.DEFAULT_NUMERIC_AGG)
    string_agg = method_config.get("string_agg", config.DEFAULT_STRING_AGG)
    return numeric_agg, string_agg


def _load_target_geometries(date_to):
    """Load the date_to reference GeoJSON and index geometries by admin code.

    Args:
        date_to: str -- target version date, format YYYYMMDD.

    Returns:
        dict: {code: geometry_dict, ...}.
    """
    geojson_path = config.GEOJSON_DIR / ("ver%s.geojson" % date_to)
    geometries = {}

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for feature in data.get("features", []):
        properties = normalizer.normalize_columns(feature.get("properties", {}))
        code = properties.get(config.ADM_CODE_FIELD)
        if code is not None:
            geometries[code] = feature["geometry"]

    return geometries


def _collect_merge_group(features, merged_seen, group_code_to, synthesized):
    """Collect every not-yet-processed Feature whose mapping target is group_code_to.

    Args:
        features: list[dict] -- full input Feature list.
        merged_seen: set[str] -- code_from values already grouped/processed.
        group_code_to: str -- target code_to shared by the merge group.
        synthesized: dict -- resolver.synthesize_chain() result.

    Returns:
        tuple(list[dict], list[tuple]): (group_features, group_members) where
            group_members is [(row_index, code_from, weight), ...].
    """
    group_features = []
    group_members = []

    for row_index, feature in enumerate(features):
        code_from = feature["properties"][config.ADM_CODE_FIELD]

        if code_from in merged_seen:
            continue

        entries = synthesized.get(code_from)
        if not entries:
            continue

        code_to, weight, change_type = entries[0]
        if change_type != config.CHANGE_TYPE_MERGE or code_to != group_code_to:
            continue

        group_features.append(feature)
        group_members.append((row_index, code_from, weight))

    return group_features, group_members


def convert(input_file, date_from, date_to, method_config, output_file):
    """Run the Pipeline B entry point end-to-end.

    Calls reader -> resolver -> normalizer (via reader) -> method_recode/
    method_split/method_merge -> logger -> writer in order, converting an
    input GeoJSON and producing a conversion_log.csv alongside the output.

    Args:
        input_file: str|pathlib.Path -- input GeoJSON path.
        date_from: str -- start version date, format YYYYMMDD.
        date_to: str -- end version date, format YYYYMMDD.
        method_config: dict -- e.g. {"numeric_agg": "sum", "string_agg": "first"}.
            Missing keys are filled from config.DEFAULT_NUMERIC_AGG /
            config.DEFAULT_STRING_AGG.
        output_file: str|pathlib.Path -- output GeoJSON path.

    Returns:
        tuple(str, str): (output_file absolute path, conversion_log absolute path).

    Raises:
        RuntimeError: propagated from ConversionLogger.log_error_and_halt()
            when a code_from has no mapping or change_type == COMPLEX
            (config.HALT_ON_ERROR == True).
    """
    numeric_agg, string_agg = _resolve_method_config(method_config)

    features = reader.read_input(input_file)

    chain_files = resolver.resolve_chain(date_from, date_to)
    mapping_tables = [resolver.load_mapping_table(f) for f in chain_files]
    synthesized = resolver.synthesize_chain(mapping_tables)

    conv_logger = conv_logger_module.ConversionLogger()
    target_geometries = None

    result_features = []
    merged_seen = set()

    for row_index, feature in enumerate(features):
        code_from = feature["properties"][config.ADM_CODE_FIELD]

        if code_from in merged_seen:
            continue

        entries = synthesized.get(code_from)

        if not entries:
            conv_logger.log_error_and_halt(
                row_index, code_from,
                "No mapping found for code_from='%s'" % code_from,
            )

        change_type = entries[0][2]

        if change_type == config.CHANGE_TYPE_COMPLEX:
            conv_logger.log_error_and_halt(
                row_index, code_from,
                "change_type=COMPLEX is not supported in BETA stage for "
                "code_from='%s'" % code_from,
            )

        elif change_type == config.CHANGE_TYPE_PASS:
            code_to, weight, _ = entries[0]
            new_feature = method_recode.apply_recode(feature, code_to)
            result_features.append(new_feature)
            conv_logger.log_record(
                row_index, code_from, code_to, change_type,
                "method_recode", weight, "OK",
            )

        elif change_type == config.CHANGE_TYPE_SPLIT:
            if target_geometries is None:
                target_geometries = _load_target_geometries(date_to)

            split_targets = [(code_to, weight) for code_to, weight, _ in entries]
            new_features = method_split.apply_split(
                feature, split_targets, numeric_agg, string_agg, target_geometries,
            )
            result_features.extend(new_features)

            for code_to, weight in split_targets:
                conv_logger.log_record(
                    row_index, code_from, code_to, change_type,
                    "method_split", weight, "OK",
                )

        elif change_type == config.CHANGE_TYPE_MERGE:
            code_to = entries[0][0]

            group_features, group_members = _collect_merge_group(
                features, merged_seen, code_to, synthesized,
            )

            merged_feature = method_merge.apply_merge(
                group_features, code_to, numeric_agg, string_agg,
            )
            result_features.append(merged_feature)

            for member_row_index, member_code_from, member_weight in group_members:
                merged_seen.add(member_code_from)
                conv_logger.log_record(
                    member_row_index, member_code_from, code_to, change_type,
                    "method_merge", member_weight, "OK",
                )

        else:
            conv_logger.log_error_and_halt(
                row_index, code_from,
                "Unknown change_type '%s' for code_from='%s'" % (change_type, code_from),
            )

    output_absolute_path = writer.write_output(result_features, output_file, source_metadata={})

    log_path = pathlib.Path(output_absolute_path).parent / "conversion_log.csv"
    log_absolute_path = conv_logger.save_log(log_path)

    return output_absolute_path, log_absolute_path
