import csv
import pathlib
import config


class ConversionLogger:
    """Accumulate conversion log records and persist them to CSV.

    The class keeps state (accumulated records) across multiple
    log_record() / log_error_and_halt() calls, which a plain module-level
    list would make awkward to reset between runs.
    """

    def __init__(self):
        self._records = []

    def log_record(self, row_index, code_from, code_to, change_type, method, weight, status):
        """Append one record to the internal record list.

        For SPLIT, this may be called multiple times with the same
        row_index, producing multiple accumulated rows.

        Args:
            row_index: int -- source row/feature index.
            code_from: str -- administrative code before conversion.
            code_to: str -- administrative code after conversion.
            change_type: str -- config.CHANGE_TYPE_* label.
            method: str -- method function name used (e.g. "method_recode").
            weight: float|None -- conversion weight, if applicable.
            status: str -- "OK" / "ERROR" / etc.
        """
        record = {
            "row_index": row_index,
            "code_from": code_from,
            "code_to": code_to,
            "change_type": change_type,
            "method": method,
            "weight": weight,
            "status": status,
        }
        self._records.append(record)

    def log_error_and_halt(self, row_index, code_from, reason):
        """Record an ERROR row and immediately halt processing.

        Args:
            row_index: int -- source row/feature index.
            code_from: str -- administrative code that triggered the error.
            reason: str -- human-readable error reason, used as the
                RuntimeError message.

        Raises:
            RuntimeError: always, after the ERROR record has been logged.
        """
        self.log_record(
            row_index, code_from, code_to="", change_type="",
            method="", weight=None, status="ERROR",
        )
        raise RuntimeError(reason)

    def save_log(self, output_path):
        """Save accumulated records as a UTF-8 CSV file.

        Args:
            output_path: str|pathlib.Path -- destination CSV path.
                Parent directories are created if missing.

        Returns:
            str: absolute path of the saved CSV file.
        """
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=config.CONVERSION_LOG_COLUMNS)
            writer.writeheader()
            for record in self._records:
                writer.writerow(record)

        return str(output_path.resolve())
