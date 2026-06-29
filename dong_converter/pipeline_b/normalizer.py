import logging
import config

logger = logging.getLogger(__name__)


def normalize_columns(feature_properties):
    """Normalize Feature properties column names using config.COLUMN_ALIASES.

    Args:
        feature_properties: dict — original properties dict of a Feature.

    Returns:
        dict: a new properties dict with alias column names normalized.
              The original dict is not mutated.
    """
    normalized = dict(feature_properties)

    for old_column, new_column in config.COLUMN_ALIASES.items():
        if old_column in normalized and new_column not in normalized:
            normalized[new_column] = normalized.pop(old_column)
            logger.debug(
                "Renamed column '%s' -> '%s'", old_column, new_column
            )

    return normalized


def normalize_code(code):
    """Normalize an administrative code to the 10-digit standard format.

    Args:
        code: str — administrative code to normalize.

    Returns:
        str: the 10-digit standard code.

    Raises:
        NotImplementedError: If an 8-digit code is given. BETA stage does not
            implement the actual 8-digit -> 10-digit conversion table lookup;
            only the structure is in place. ALPHA stage is expected to wire
            in the real conversion logic here.
        ValueError: If the code is not a 10-digit or 8-digit numeric string.
    """
    if len(code) == 10 and code.isdigit():
        return code

    if len(code) == 8 and code.isdigit():
        # BETA: conversion table lookup is not implemented yet.
        # ALPHA stage will replace this with the real 8-digit -> 10-digit
        # conversion table lookup.
        raise NotImplementedError(
            "8-digit code conversion is not implemented in BETA stage: '%s'" % code
        )

    raise ValueError("Invalid administrative code format: '%s'" % code)
