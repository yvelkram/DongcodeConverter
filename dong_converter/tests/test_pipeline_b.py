import copy
import csv
import json
import pathlib
import pytest
import pipeline_b.normalizer as normalizer
import pipeline_b.resolver as resolver
import pipeline_b.reader as reader
import pipeline_b.converter as converter
import methods.method_recode as method_recode
import methods.method_split as method_split
import methods.method_merge as method_merge
import logger
import config
import main

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROPERTIES_OLD_ALIAS = {"adm_cd": "1111010100"}
SAMPLE_PROPERTIES_STANDARD = {"adm_cd2": "1111010100"}


# ---------------------------------------------------------------------------
# TC-B-01: normalizer column alias handling
# ---------------------------------------------------------------------------

def test_tc_b01():
    """TC-B-01: Verify normalize_columns() and normalize_code() behavior."""

    result = normalizer.normalize_columns(SAMPLE_PROPERTIES_OLD_ALIAS)
    assert "adm_cd2" in result
    assert result["adm_cd2"] == "1111010100"
    assert "adm_cd" not in result

    assert SAMPLE_PROPERTIES_OLD_ALIAS == {"adm_cd": "1111010100"}

    result_standard = normalizer.normalize_columns(SAMPLE_PROPERTIES_STANDARD)
    assert result_standard == SAMPLE_PROPERTIES_STANDARD

    assert normalizer.normalize_code("1111010100") == "1111010100"

    with pytest.raises(NotImplementedError):
        normalizer.normalize_code("12345678")

    with pytest.raises(ValueError):
        normalizer.normalize_code("123")


# ---------------------------------------------------------------------------
# TC-B-02: resolver single-range mapping table load
# ---------------------------------------------------------------------------

def test_tc_b02():
    """TC-B-02: Verify load_mapping_table() against the pilot mapping table."""

    filename = "map_20241231_20250101.csv"
    path = config.TRANSITIONS_DIR / filename
    if not path.exists():
        pytest.skip("Pilot mapping table not found: %s" % filename)

    records = resolver.load_mapping_table(filename)

    assert len(records) == 3555

    pass_count = sum(1 for r in records if r["change_type"] == "PASS")
    split_count = sum(1 for r in records if r["change_type"] == "SPLIT")

    assert pass_count == 3553
    assert split_count == 2


# ---------------------------------------------------------------------------
# TC-B-03: resolver chain synthesis (synthetic data)
# ---------------------------------------------------------------------------

def test_tc_b03():
    """TC-B-03: Verify synthesize_chain() two-stage chain synthesis logic."""

    map_a_b = [
        {"code_from": "X", "code_to": "Z", "change_type": "PASS",
         "weight": 1.0, "warn_flag": 0},
    ]
    map_b_c = [
        {"code_from": "Z", "code_to": "Y", "change_type": "PASS",
         "weight": 1.0, "warn_flag": 0},
        {"code_from": "Z", "code_to": "W", "change_type": "SPLIT",
         "weight": 0.6, "warn_flag": 0},
        {"code_from": "Z", "code_to": "V", "change_type": "SPLIT",
         "weight": 0.4, "warn_flag": 0},
    ]

    result = resolver.synthesize_chain([map_a_b, map_b_c])

    assert "X" in result

    entries = result["X"]
    split_entries = [e for e in entries if e[2] == "SPLIT"]
    pass_entries = [e for e in entries if e[2] == "PASS"]

    assert pass_entries or split_entries

    if split_entries:
        weight_sum = sum(weight for _, weight, _ in split_entries)
        assert abs(weight_sum - 1.0) <= 0.01

    if pass_entries:
        for _, weight, _ in pass_entries:
            assert abs(weight - 1.0) <= 0.01


# ---------------------------------------------------------------------------
# resolve_chain(): error handling
# ---------------------------------------------------------------------------

def test_resolve_chain_errors():
    """resolve_chain() must raise ValueError on same-date or reversed input."""

    with pytest.raises(ValueError):
        resolver.resolve_chain("20241231", "20241231")

    with pytest.raises(ValueError):
        resolver.resolve_chain("20250101", "20241231")


# ---------------------------------------------------------------------------
# TC-B-04: method_recode PASS handling
# ---------------------------------------------------------------------------

def test_tc_b04():
    """TC-B-04: Verify apply_recode() replaces only the admin code field."""

    original_feature = {
        "type": "Feature",
        "properties": {
            "adm_cd2": "1111010100",
            "adm_nm": "Sample Dong",
            "sgg": "11110",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[126.9, 37.5], [127.0, 37.5], [127.0, 37.6], [126.9, 37.5]]
            ],
        },
    }
    original_snapshot = copy.deepcopy(original_feature)

    result = method_recode.apply_recode(original_feature, "1111010200")

    assert result["properties"][config.ADM_CODE_FIELD] == "1111010200"
    assert result["properties"]["adm_nm"] == original_feature["properties"]["adm_nm"]
    assert result["properties"]["sgg"] == original_feature["properties"]["sgg"]

    assert result["geometry"] == original_snapshot["geometry"]

    assert original_feature == original_snapshot


# ---------------------------------------------------------------------------
# TC-B-05: method_split SPLIT handling (pilot data)
# ---------------------------------------------------------------------------

def test_tc_b05():
    """TC-B-05: Verify apply_split() against the pilot Nogsan-dong split."""

    fixture_path = config.BASE_DIR / "tests" / "fixtures" / "ver20241231_sample.geojson"
    if not fixture_path.exists():
        pytest.skip("Test fixture not found: %s" % fixture_path)

    mapping_filename = "map_20241231_20250101.csv"
    mapping_path = config.TRANSITIONS_DIR / mapping_filename
    if not mapping_path.exists():
        pytest.skip("Pilot mapping table not found: %s" % mapping_filename)

    target_geojson_path = config.GEOJSON_DIR / "ver20250101.geojson"
    if not target_geojson_path.exists():
        pytest.skip("Target reference GeoJSON not found: %s" % target_geojson_path)

    features = reader.read_input(fixture_path)
    source_feature = None
    for feature in features:
        if feature["properties"][config.ADM_CODE_FIELD] == "2644056000":
            source_feature = feature
            break
    assert source_feature is not None

    records = resolver.load_mapping_table(mapping_filename)
    split_records = [
        r for r in records
        if r["code_from"] == "2644056000" and r["change_type"] == "SPLIT"
    ]
    assert len(split_records) == 2
    split_targets = [(r["code_to"], r["weight"]) for r in split_records]

    target_geometries = {}
    with open(target_geojson_path, "r", encoding="utf-8") as f:
        target_data = json.load(f)
    wanted_codes = {code_to for code_to, _ in split_targets}
    for feature in target_data["features"]:
        code = feature["properties"].get("adm_cd2") or feature["properties"].get("adm_cd")
        if code in wanted_codes:
            target_geometries[code] = feature["geometry"]
    assert set(target_geometries.keys()) == wanted_codes

    result = method_split.apply_split(
        source_feature, split_targets, config.DEFAULT_NUMERIC_AGG,
        config.DEFAULT_STRING_AGG, target_geometries,
    )

    assert len(result) == len(split_targets)

    original_properties = source_feature["properties"]
    for new_feature, (code_to, weight) in zip(result, split_targets):
        assert new_feature["properties"][config.ADM_CODE_FIELD] == code_to

        for column, value in original_properties.items():
            if column == config.ADM_CODE_FIELD:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            assert abs(new_feature["properties"][column] - numeric_value * weight) <= 1e-6

    with pytest.raises(NotImplementedError):
        method_split.apply_split(
            source_feature, split_targets, "weighted_mean",
            config.DEFAULT_STRING_AGG, target_geometries,
        )


# ---------------------------------------------------------------------------
# TC-B-06: method_merge MERGE handling (synthetic data)
# ---------------------------------------------------------------------------

def test_tc_b06():
    """TC-B-06: Verify apply_merge() numeric/string aggregation and geometry."""

    feature_a = {
        "type": "Feature",
        "properties": {"population": 100, "name": "A"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
            ],
        },
    }
    feature_b = {
        "type": "Feature",
        "properties": {"population": 200, "name": "B"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]
            ],
        },
    }
    features = [feature_a, feature_b]

    result_sum_first = method_merge.apply_merge(features, "9999999999", "sum", "first")
    assert isinstance(result_sum_first, dict)
    assert result_sum_first["properties"]["population"] == 300
    assert result_sum_first["properties"]["name"] == "A"
    assert result_sum_first["properties"][config.ADM_CODE_FIELD] == "9999999999"

    result_concat = method_merge.apply_merge(features, "9999999999", "sum", "concat")
    assert result_concat["properties"]["name"] == "A/B"

    with pytest.raises(NotImplementedError):
        method_merge.apply_merge(features, "9999999999", "weighted_mean", "first")


# ---------------------------------------------------------------------------
# TC-B-07: logger ERROR immediate halt
# ---------------------------------------------------------------------------

def test_tc_b07(tmp_path):
    """TC-B-07: Verify ConversionLogger error halting and CSV output."""

    conv_logger = logger.ConversionLogger()

    # Assume a COMPLEX-type or no-mapping situation triggers an immediate halt.
    with pytest.raises(RuntimeError):
        conv_logger.log_error_and_halt(0, "1111010100", "No mapping found for code_from")

    assert len(conv_logger._records) == 1
    error_record = conv_logger._records[0]
    assert error_record["status"] == "ERROR"
    assert error_record["code_from"] == "1111010100"
    assert error_record["code_to"] == ""
    assert error_record["change_type"] == ""
    assert error_record["method"] == ""
    assert error_record["weight"] is None

    # Normal log_record() calls accumulate further rows.
    conv_logger.log_record(1, "X", "Y", "PASS", "method_recode", 1.0, "OK")

    # SPLIT scenario: same row_index logged twice -> two rows in the CSV.
    conv_logger.log_record(2, "Z", "W", "SPLIT", "method_split", 0.6, "OK")
    conv_logger.log_record(2, "Z", "V", "SPLIT", "method_split", 0.4, "OK")

    output_path = tmp_path / "conversion_log.csv"
    saved_path = conv_logger.save_log(output_path)

    with open(saved_path, "r", encoding="utf-8", newline="") as f:
        reader_csv = csv.reader(f)
        rows = list(reader_csv)

    header = rows[0]
    assert header == config.CONVERSION_LOG_COLUMNS

    data_rows = rows[1:]
    assert len(data_rows) == 4

    split_rows = [row for row in data_rows if row[0] == "2"]
    assert len(split_rows) == 2


# ---------------------------------------------------------------------------
# TC-B-08: converter integration run (pilot)
# ---------------------------------------------------------------------------

def test_tc_b08(tmp_path):
    """TC-B-08: Verify convert() end-to-end pipeline integration (pilot data)."""

    mapping_filename = "map_20241231_20250101.csv"
    mapping_path = config.TRANSITIONS_DIR / mapping_filename
    if not mapping_path.exists():
        pytest.skip("Pilot mapping table not found: %s" % mapping_filename)

    input_file = config.BASE_DIR / "tests" / "fixtures" / "ver20241231_sample.geojson"
    if not input_file.exists():
        pytest.skip("Test fixture not found: %s" % input_file)

    with open(input_file, "r", encoding="utf-8") as f:
        input_feature_count = len(json.load(f)["features"])

    output_file = tmp_path / "converted.geojson"

    output_path, log_path = converter.convert(
        input_file, "20241231", "20250101", {}, output_file
    )

    output_path = pathlib.Path(output_path)
    assert output_path.exists()

    with open(output_path, "r", encoding="utf-8") as f:
        output_data = json.load(f)
    assert len(output_data["features"]) >= input_feature_count

    log_file_path = output_path.parent / "conversion_log.csv"
    assert log_file_path.exists()
    assert str(log_file_path.resolve()) == log_path

    with open(log_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    assert header == config.CONVERSION_LOG_COLUMNS

    split_rows = [
        row for row in rows[1:]
        if row[1] == "2644056000" and row[3] == config.CHANGE_TYPE_SPLIT
    ]
    assert len(split_rows) >= 2


# ---------------------------------------------------------------------------
# TC-B-09: main.py E2E (Pipeline A -> Pipeline B linkage)
# ---------------------------------------------------------------------------

def test_tc_b09(tmp_path):
    """TC-B-09: Verify run_pipeline_a() -> run_pipeline_b() linkage via main.py."""

    path_before = config.GEOJSON_DIR / "ver20241231.geojson"
    path_after = config.GEOJSON_DIR / "ver20250101.geojson"

    # Skip gracefully if pilot files are not present (same precondition as TC-A-09)
    if not path_before.exists() or not path_after.exists():
        pytest.skip("Pilot GeoJSON files not found; skipping TC-B-09")

    date_before = "20241231"
    date_after = "20250101"

    # Step 1: run Pipeline A and obtain the transition table CSV path
    transition_csv_path = main.run_pipeline_a(
        path_before, path_after, date_before, date_after
    )

    transition_csv_path_obj = pathlib.Path(transition_csv_path)
    assert transition_csv_path_obj.exists(), (
        "Pipeline A output CSV must exist at: %s" % transition_csv_path
    )

    # Step 2: run Pipeline B reusing the same date_from/date_to pair so the
    # resolver picks up the CSV generated above from config.TRANSITIONS_DIR.
    input_file = config.BASE_DIR / "tests" / "fixtures" / "ver20241231_sample.geojson"
    if not input_file.exists():
        pytest.skip("Test fixture not found: %s" % input_file)

    output_file = tmp_path / "converted_e2e.geojson"

    output_path, log_path = main.run_pipeline_b(
        input_file, date_before, date_after, {}, output_file
    )

    output_path_obj = pathlib.Path(output_path)
    log_path_obj = pathlib.Path(log_path)

    assert output_path_obj.exists(), "Pipeline B output GeoJSON must exist at: %s" % output_path
    assert log_path_obj.exists(), "Pipeline B conversion log must exist at: %s" % log_path
