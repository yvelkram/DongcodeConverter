import copy
import config


def apply_recode(feature, code_to):
    """Apply a PASS-type recode to a Feature.

    Only the administrative code field is replaced. The geometry and every
    other property are left untouched. The original Feature is never
    mutated -- a deep copy is made first.

    Args:
        feature: dict -- original GeoJSON Feature.
        code_to: str -- new administrative code value.

    Returns:
        dict: a new Feature with properties[config.ADM_CODE_FIELD] set to
            code_to. geometry is identical to the original.
    """
    new_feature = copy.deepcopy(feature)
    new_feature["properties"][config.ADM_CODE_FIELD] = code_to
    return new_feature
