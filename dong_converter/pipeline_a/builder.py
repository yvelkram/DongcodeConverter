import csv
import logging
import pathlib

import pipeline_a.diff_engine as diff_engine
import pipeline_a.geojson_loader as geojson_loader
import config

logger = logging.getLogger(__name__)


def build_transition_table(path_before, path_after, date_before, date_after, output_dir):
    """Build a transition table CSV from two GeoJSON versions.

    Runs the full Pipeline A sequence:
        geojson_loader -> extract_code_map -> diff_engine -> CSV output

    Args:
        path_before  (str | pathlib.Path): File path to the before-version GeoJSON.
        path_after   (str | pathlib.Path): File path to the after-version GeoJSON.
        date_before  (str)               : Before version date string (YYYYMMDD).
        date_after   (str)               : After version date string (YYYYMMDD).
        output_dir   (str | pathlib.Path): Directory where the output CSV is saved.

    Returns:
        str: Absolute path of the generated CSV file.
    """
    path_before = pathlib.Path(path_before)
    path_after  = pathlib.Path(path_after)
    output_dir  = pathlib.Path(output_dir)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load GeoJSON features
    logger.info("Loading before GeoJSON: %s", path_before)
    features_before = geojson_loader.load_geojson(path_before)

    logger.info("Loading after GeoJSON: %s", path_after)
    features_after = geojson_loader.load_geojson(path_after)

    # Step 2: Extract code maps
    logger.info("Extracting code maps")
    code_map_before = geojson_loader.extract_code_map(features_before)
    code_map_after  = geojson_loader.extract_code_map(features_after)

    logger.info("Before codes: %d, After codes: %d", len(code_map_before), len(code_map_after))

    # Step 3: Classify changes
    logger.info("Classifying changes")
    records = diff_engine.classify_changes(code_map_before, code_map_after)

    # Step 4: Write CSV
    output_filename = "map_%s_%s.csv" % (date_before, date_after)
    output_csv_path = output_dir / output_filename

    with open(output_csv_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=config.TRANSITION_CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            row = dict(record)
            # Format weight with configured precision
            row["weight"] = "%.*f" % (config.WEIGHT_PRECISION, record["weight"])
            writer.writerow(row)

    # Step 5: Print processing summary
    total        = len(records)
    pass_count   = sum(1 for r in records if r["change_type"] == config.CHANGE_TYPE_PASS)
    split_count  = sum(1 for r in records if r["change_type"] == config.CHANGE_TYPE_SPLIT)
    merge_count  = sum(1 for r in records if r["change_type"] == config.CHANGE_TYPE_MERGE)
    complex_count = sum(1 for r in records if r["change_type"] == config.CHANGE_TYPE_COMPLEX)
    warn_count   = sum(1 for r in records if r["change_type"] == config.CHANGE_TYPE_WARN)

    print("[Pipeline A] 변환표 생성 완료")
    print("  버전 쌍  : %s -> %s" % (date_before, date_after))
    print("  출력 파일: %s" % str(output_csv_path.resolve()))
    print("  총 레코드: %d건" % total)
    print("  PASS     : %d건" % pass_count)
    print("  SPLIT    : %d건" % split_count)
    print("  MERGE    : %d건" % merge_count)
    print("  COMPLEX  : %d건" % complex_count)
    print("  WARN     : %d건" % warn_count)

    return str(output_csv_path.resolve())
