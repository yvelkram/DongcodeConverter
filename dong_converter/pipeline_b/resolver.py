import csv
import logging
import config

logger = logging.getLogger(__name__)


def load_version_registry():
    """Load the version registry CSV listing geojson versions in order.

    Args:
        None — uses config.VERSION_REGISTRY path.

    Returns:
        list[tuple]: [(version_date, geojson_filename), ...] in file row order.
    """
    rows = []
    with open(config.VERSION_REGISTRY, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["version_date"], row["geojson_filename"]))
    return rows


def resolve_chain(date_from, date_to):
    """Resolve the list of adjacent mapping-table filenames between two versions.

    Args:
        date_from: str — start version date, format YYYYMMDD.
        date_to: str — end version date, format YYYYMMDD.

    Returns:
        list[str]: mapping table filenames in order, e.g. ["map_a_b.csv", ...].

    Raises:
        ValueError: if date_from == date_to, or date_from comes after date_to
            in the version registry order.
    """
    if date_from == date_to:
        raise ValueError(
            "date_from and date_to must differ: '%s'" % date_from
        )

    registry = load_version_registry()
    dates = [version_date for version_date, _ in registry]

    index_from = dates.index(date_from)
    index_to = dates.index(date_to)

    if index_from > index_to:
        raise ValueError(
            "date_from('%s') comes after date_to('%s') in version registry"
            % (date_from, date_to)
        )

    filenames = []
    for i in range(index_from, index_to):
        a = dates[i]
        b = dates[i + 1]
        filenames.append("map_%s_%s.csv" % (a, b))
    return filenames


def load_mapping_table(filename):
    """Load a single mapping table CSV.

    Args:
        filename: str — "map_YYYYMMDD_YYYYMMDD.csv" format file name.

    Returns:
        list[dict]: records keyed by config.TRANSITION_CSV_COLUMNS,
            with weight as float and warn_flag as int.
    """
    path = config.TRANSITIONS_DIR / filename
    records = []
    warn_count = 0

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "code_from": row["code_from"],
                "code_to": row["code_to"],
                "change_type": row["change_type"],
                "weight": float(row["weight"]),
                "warn_flag": int(row["warn_flag"]),
            }
            if record["warn_flag"] == 1:
                warn_count += 1
            records.append(record)

    if warn_count > 0:
        logger.warning(
            "%d record(s) with warn_flag=1 found in '%s'", warn_count, filename
        )

    return records


def synthesize_chain(mapping_tables):
    """Synthesize one or more mapping tables into a code_from -> targets map.

    Args:
        mapping_tables: list[list[dict]] — list of load_mapping_table() results.

    Returns:
        dict: {code_from: [(code_to, weight, change_type), ...]}
    """
    if len(mapping_tables) == 1:
        return _group_single_table(mapping_tables[0])

    return _synthesize_two_stage_chain(mapping_tables)


def _group_single_table(table):
    """Group a single mapping table's records by code_from.

    Args:
        table: list[dict] — load_mapping_table() result.

    Returns:
        dict: {code_from: [(code_to, weight, change_type), ...]}
    """
    grouped = {}
    for record in table:
        code_from = record["code_from"]
        entry = (record["code_to"], record["weight"], record["change_type"])
        grouped.setdefault(code_from, []).append(entry)
    return grouped


def _synthesize_two_stage_chain(mapping_tables):
    """Synthesize a chain of two or more mapping tables stage by stage.

    BETA scope: only the two representative patterns are guaranteed correct:
      - PASS x PASS = PASS (weight stays 1.0)
      - PASS x SPLIT = SPLIT (weight multiplied through)
    Full chain accuracy across arbitrary change_type combinations is verified
    in the ALPHA stage.

    Args:
        mapping_tables: list[list[dict]] — list of load_mapping_table() results,
            ordered from the earliest stage to the latest.

    Returns:
        dict: {code_from: [(code_to, weight, change_type), ...]}
    """
    current = _group_single_table(mapping_tables[0])

    for next_table in mapping_tables[1:]:
        next_grouped = _group_single_table(next_table)
        merged = {}

        for code_from, intermediate_entries in current.items():
            combined = []
            for code_mid, weight_mid, change_type_mid in intermediate_entries:
                next_entries = next_grouped.get(code_mid, [])
                for code_to, weight_next, change_type_next in next_entries:
                    weight_combined = weight_mid * weight_next
                    change_type_combined = change_type_next
                    if change_type_mid != config.CHANGE_TYPE_PASS:
                        change_type_combined = change_type_mid
                    combined.append((code_to, weight_combined, change_type_combined))
            merged[code_from] = combined

        current = merged

    return current
