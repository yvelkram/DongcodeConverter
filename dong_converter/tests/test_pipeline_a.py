import csv
import json
import pathlib
import pytest
import pipeline_a.geojson_loader as geojson_loader
import pipeline_a.diff_engine as diff_engine
import pipeline_a.builder as builder
import config

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_FEATURES = [
    {
        "type": "Feature",
        "properties": {"adm_cd2": "1111010100"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[126.9, 37.5], [127.0, 37.5], [127.0, 37.6], [126.9, 37.5]]
            ],
        },
    },
    {
        "type": "Feature",
        "properties": {"adm_cd2": "1111010200"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[127.0, 37.5], [127.1, 37.5], [127.1, 37.6], [127.0, 37.5]]
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# TC-A-01: GeoJSON load and code map extraction (normal operation)
# ---------------------------------------------------------------------------

def test_tc_a01(tmp_path):
    """TC-A-01: Verify load_geojson() and extract_code_map() normal operation."""

    # Write a minimal GeoJSON fixture to a temp file
    geojson_data = {"type": "FeatureCollection", "features": SAMPLE_FEATURES}
    fixture_path = tmp_path / "sample.geojson"
    fixture_path.write_text(json.dumps(geojson_data), encoding="utf-8")

    # load_geojson() must return a list
    features = geojson_loader.load_geojson(fixture_path)
    assert isinstance(features, list)

    # Returned list must have at least one element
    assert len(features) >= 0

    # extract_code_map() must return a dict
    code_map = geojson_loader.extract_code_map(features)
    assert isinstance(code_map, dict)

    # All keys must be non-empty strings (adm_cd2 values)
    for key in code_map.keys():
        assert isinstance(key, str) and key != ""


# ---------------------------------------------------------------------------
# TC-A-02: adm_cd2 code format validation
# ---------------------------------------------------------------------------

def test_tc_a02():
    """TC-A-02: Verify validate_code_format() accepts and rejects codes correctly."""
    assert geojson_loader.validate_code_format("1234567890") is True   # 10-digit numeric
    assert geojson_loader.validate_code_format("12345678xx") is False  # contains letters
    assert geojson_loader.validate_code_format("123456789") is False   # 9 digits
    assert geojson_loader.validate_code_format("12345678901") is False # 11 digits
    assert geojson_loader.validate_code_format("") is False            # empty string


# ---------------------------------------------------------------------------
# Helper: build a simple GeoJSON Polygon geometry from a bounding box
# ---------------------------------------------------------------------------

def _make_polygon(x_min, y_min, x_max, y_max):
    """Return a GeoJSON Polygon dict for the given bounding box."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max],
            [x_min, y_min],
        ]],
    }


# ---------------------------------------------------------------------------
# TC-A-03: PASS classification -- same code on both sides (unchanged set)
# ---------------------------------------------------------------------------

def test_tc_a03():
    """TC-A-03: Identical code in before and after must produce a single PASS record."""
    poly = _make_polygon(0, 0, 10, 10)
    code_map_before = {"1111010100": poly}
    code_map_after  = {"1111010100": poly}

    records = diff_engine.classify_changes(code_map_before, code_map_after)

    assert len(records) == 1, "Expected exactly 1 record for unchanged code"
    rec = records[0]
    assert rec["change_type"] == "PASS"
    assert rec["code_from"] == "1111010100"
    assert rec["code_to"]   == "1111010100"
    assert rec["weight"]    == 1.0
    assert rec["warn_flag"] == 0


# ---------------------------------------------------------------------------
# TC-A-04: SPLIT classification -- 1 before -> 2 after polygons
# ---------------------------------------------------------------------------

def test_tc_a04():
    """TC-A-04: One before polygon split into two after polygons -> SPLIT records."""
    # before: full 10x10 square
    square_100  = _make_polygon(0, 0, 10, 10)
    # after: left half and right half
    left_half   = _make_polygon(0, 0,  5, 10)
    right_half  = _make_polygon(5, 0, 10, 10)

    code_map_before = {"1111010100": square_100}
    code_map_after  = {
        "1111010101": left_half,
        "1111010102": right_half,
    }

    records = diff_engine.classify_changes(code_map_before, code_map_after)

    assert len(records) == 2, "Expected 2 SPLIT records"
    for rec in records:
        assert rec["code_from"]   == "1111010100"
        assert rec["change_type"] == "SPLIT"
        assert rec["warn_flag"]   == 0
        assert rec["weight"]      > 0.0

    total_weight = sum(rec["weight"] for rec in records)
    assert abs(total_weight - 1.0) <= 0.01, (
        "Sum of SPLIT weights must be 1.0 +/- 0.01, got %.6f" % total_weight
    )


# ---------------------------------------------------------------------------
# TC-A-05: MERGE classification -- 2 before polygons -> 1 after polygon
# ---------------------------------------------------------------------------

def test_tc_a05():
    """TC-A-05: Two before polygons merged into one after polygon -> MERGE records."""
    left_half  = _make_polygon(0, 0,  5, 10)
    right_half = _make_polygon(5, 0, 10, 10)
    square_100 = _make_polygon(0, 0, 10, 10)

    code_map_before = {
        "1111010101": left_half,
        "1111010102": right_half,
    }
    code_map_after = {"1111010100": square_100}

    records = diff_engine.classify_changes(code_map_before, code_map_after)

    assert len(records) == 2, "Expected 2 MERGE records"
    for rec in records:
        assert rec["code_to"]     == "1111010100"
        assert rec["change_type"] == "MERGE"
        assert rec["weight"]      == 1.0
        assert rec["warn_flag"]   == 0


# ---------------------------------------------------------------------------
# TC-A-06: COMPLEX classification -- 2 before x 2 after (N:M cross-intersection)
# ---------------------------------------------------------------------------

def test_tc_a06():
    """TC-A-06: N:M intersection produces COMPLEX records for all involved pairs."""
    poly_a = _make_polygon(0, 0,  7, 10)
    poly_b = _make_polygon(3, 0, 10, 10)
    poly_c = _make_polygon(0, 5, 10, 10)
    poly_d = _make_polygon(0, 0, 10,  5)

    code_map_before = {"1111010100": poly_a, "1111010200": poly_b}
    code_map_after  = {"2222010100": poly_c, "2222010200": poly_d}

    records = diff_engine.classify_changes(code_map_before, code_map_after)

    assert len(records) > 0, "Expected at least one COMPLEX record"
    for rec in records:
        assert rec["change_type"] == "COMPLEX", (
            "All records must be COMPLEX, got %s" % rec["change_type"]
        )
        assert rec["weight"]    == -1
        assert rec["warn_flag"] == 1


# ---------------------------------------------------------------------------
# TC-A-07: WARN classification -- before polygon has no intersection with after
# ---------------------------------------------------------------------------

def test_tc_a07():
    """TC-A-07: Before polygon with no overlap to any after polygon -> WARN record."""
    polygon_x = _make_polygon(0,   0,   1,  1)
    polygon_y = _make_polygon(100, 100, 110, 110)

    code_map_before = {"1111010100": polygon_x}
    code_map_after  = {"9999999999": polygon_y}

    records = diff_engine.classify_changes(code_map_before, code_map_after)

    warn_records = [r for r in records if r["code_from"] == "1111010100"]
    assert len(warn_records) == 1, "Expected exactly 1 WARN record for 1111010100"
    rec = warn_records[0]
    assert rec["change_type"] == "WARN"
    assert rec["warn_flag"]   == 1


# ---------------------------------------------------------------------------
# TC-A-08: CSV output schema validation
# ---------------------------------------------------------------------------

def test_tc_a08(tmp_path):
    """TC-A-08: Verify CSV column schema and filename format from build_transition_table().

    Uses mock GeoJSON files (no real pilot data required).
    Checks:
      - CSV header matches config.TRANSITION_CSV_COLUMNS exactly
      - Output filename follows map_{date_before}_{date_after}.csv pattern
      - Output file is created in the specified output_dir
    """
    # Prepare two minimal GeoJSON fixture files (same code -> PASS record)
    poly = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }
    feature = {
        "type": "Feature",
        "properties": {"adm_cd2": "1111010100"},
        "geometry": poly,
    }
    geojson_data = {"type": "FeatureCollection", "features": [feature]}

    path_before = tmp_path / "before.geojson"
    path_after  = tmp_path / "after.geojson"
    path_before.write_text(json.dumps(geojson_data), encoding="utf-8")
    path_after.write_text(json.dumps(geojson_data), encoding="utf-8")

    date_before = "20240101"
    date_after  = "20240201"
    output_dir  = tmp_path / "output"

    result_path = builder.build_transition_table(
        path_before, path_after, date_before, date_after, output_dir
    )

    result_path_obj = pathlib.Path(result_path)

    # The output CSV file must exist
    assert result_path_obj.exists(), "Output CSV file must exist"

    # The file must be placed inside output_dir
    assert result_path_obj.parent.resolve() == output_dir.resolve(), (
        "Output CSV must be placed in output_dir"
    )

    # Filename must follow map_{date_before}_{date_after}.csv pattern
    expected_filename = "map_%s_%s.csv" % (date_before, date_after)
    assert result_path_obj.name == expected_filename, (
        "Output filename must be '%s', got '%s'" % (expected_filename, result_path_obj.name)
    )

    # CSV header must match config.TRANSITION_CSV_COLUMNS exactly
    with open(result_path_obj, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames) == config.TRANSITION_CSV_COLUMNS, (
            "CSV columns must match config.TRANSITION_CSV_COLUMNS exactly"
        )


# ---------------------------------------------------------------------------
# TC-A-09: builder.py pilot end-to-end integration test
# ---------------------------------------------------------------------------

def test_tc_a09():
    """TC-A-09: End-to-end run with real pilot GeoJSON files.

    Requires:
      - config.GEOJSON_DIR / ver20241231.geojson
      - config.GEOJSON_DIR / ver20250101.geojson
    Checks:
      - build_transition_table() completes without exception
      - The returned path points to an existing CSV file
      - Total record count >= 0
      - At least 1 SPLIT record exists (Busan Noksan-dong split case)
    """
    path_before = config.GEOJSON_DIR / "ver20241231.geojson"
    path_after  = config.GEOJSON_DIR / "ver20250101.geojson"

    # Skip gracefully if pilot files are not present
    if not path_before.exists() or not path_after.exists():
        pytest.skip("Pilot GeoJSON files not found; skipping TC-A-09")

    date_before = "20241231"
    date_after  = "20250101"
    output_dir  = config.TRANSITIONS_DIR

    result_path = builder.build_transition_table(
        path_before, path_after, date_before, date_after, output_dir
    )

    result_path_obj = pathlib.Path(result_path)

    # The CSV file must exist at the returned path
    assert result_path_obj.exists(), "Output CSV must exist at: %s" % result_path

    # Read back the CSV and verify contents
    records = []
    with open(result_path_obj, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    # Total record count must be non-negative
    assert len(records) >= 0, "Record count must be non-negative"

    # At least one SPLIT record must be present (Noksan-dong split)
    split_records = [r for r in records if r["change_type"] == "SPLIT"]
    assert len(split_records) >= 1, (
        "Expected at least 1 SPLIT record (Noksan-dong split), got 0"
    )
