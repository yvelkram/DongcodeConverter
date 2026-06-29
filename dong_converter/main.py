import pipeline_a.builder as builder
import pipeline_b.converter as converter
import config


def run_pipeline_a(path_before, path_after, date_before, date_after):
    """Run Pipeline A: build a transition table CSV from two GeoJSON versions.

    Delegates to builder.build_transition_table() using config.TRANSITIONS_DIR
    as the output directory.

    Args:
        path_before (str | pathlib.Path): File path to the before-version GeoJSON.
        path_after  (str | pathlib.Path): File path to the after-version GeoJSON.
        date_before (str): Before version date string (YYYYMMDD).
        date_after  (str): After version date string (YYYYMMDD).

    Returns:
        str: Absolute path of the generated CSV file.
    """
    return builder.build_transition_table(
        path_before, path_after, date_before, date_after, config.TRANSITIONS_DIR
    )


def run_pipeline_b(input_file, date_from, date_to, method_config, output_file):
    """Run Pipeline B: convert an input GeoJSON using the transition mapping chain.

    Delegates to converter.convert().

    Args:
        input_file (str | pathlib.Path): Input GeoJSON path.
        date_from (str): Start version date, format YYYYMMDD.
        date_to (str): End version date, format YYYYMMDD.
        method_config (dict): Aggregation options, e.g.
            {"numeric_agg": "sum", "string_agg": "first"}.
        output_file (str | pathlib.Path): Output GeoJSON path.

    Returns:
        tuple(str, str): (output_file absolute path, conversion_log absolute path).
    """
    return converter.convert(input_file, date_from, date_to, method_config, output_file)
