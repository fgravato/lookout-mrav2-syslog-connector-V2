"""
Module containing event translation utility functions which are useful for
all event formats
"""

import json
from collections.abc import MutableMapping
from typing import Union

# Argument lengths for supported data mappings
# (oldKey, newKey): {'oldKey': val} -> {'newKey': val}
KEY_CHANGE = 2
# (oldKey, newKey, lambda val: newVal): {'oldKey: val} -> {'newKey': newVal}
KEY_VALUE_CHANGE = 3
# (oldKey0, oldKey1, newKey, lambda val0, val1: newVal) : {'oldKey0': val0, 'oldKey1': val1} -> {'newKey': newVal}
KEY_PAIR_VALUE_CHANGE = 4

# Maximum number of matches when limiting matches
MAX_MATCHES = 10
MISSING_FIELD_TEXT = "na"

MAPPING_TYPES = {
    KEY_CHANGE: lambda event, oldKey, newKey: (newKey, event[oldKey]),
    KEY_VALUE_CHANGE: lambda event, oldKey, newKey, mapping: (newKey, mapping(event[oldKey])),
    KEY_PAIR_VALUE_CHANGE: lambda event, oldKey0, oldKey1, newKey, mapping: (
        newKey,
        mapping(event[oldKey0], event[oldKey1]),
    ),
}


def flatten_event(
    raw_event: dict,
    use_match_limit: bool = True,
    remove_unicode: bool = False,
    parent_key: str = "",
    sep: str = "_",
) -> dict:
    """
    Flatten a raw event into a single level dictionary.

    Args:
        raw_event (dict): Unprocessed event dict.
        use_match_limit (bool, optional): Limit number of matches. Defaults to True.
        remove_unicode (bool, optional): Remove unicode encoding. Defaults to False.
        parent_key (str, optional): Key of a child dict within a parent. Defaults to "".
        sep (str, optional): Seperator used when flatten lower dict levels. Defaults to "_".

    Returns:
        dict: Single level dictionary representation of raw_event
    """
    flat_event = {}
    for key, val in raw_event.items():
        new_key = format_unicode_string(
            parent_key + sep + key if parent_key else key,
            remove_unicode,
        )

        if key == "matches":
            val = handle_matches(val, use_match_limit, remove_unicode)
        else:
            val = format_unicode_string(val, remove_unicode)

        if isinstance(val, MutableMapping):
            flat_event.update(flatten_event(val, use_match_limit, remove_unicode, new_key, sep))
        elif isinstance(val, list) and all(isinstance(i, (float, int, bool, str)) for i in val):
            flat_event[new_key] = ",".join(val)
        else:
            flat_event[new_key] = val
    return flat_event


def flatten_event_as_str(raw_event: dict) -> str:
    """
    Flatten an event and format it as a string.

    Args:
        raw_event (dict): Unprocessed event dict.

    Returns:
        str: Flattened event as a string.
    """
    return json.dumps(flatten_event(raw_event))


def format_unicode_string(input_str: Union[str, bytes], remove_unicode: bool) -> Union[str, bytes]:
    """
    Returns input_str as bytes if it is a unicode str and remove_unicode is true.

    Args:
        value (Union[str, bytes]): String value to be formatted.
        remove_unicode (bool): If unicode should be removed.

    Returns:
        Union[str, bytes]: Either a bytes or str representation of input_str.
    """
    if remove_unicode and isinstance(input_str, str):
        return input_str.encode("utf-8")
    return input_str


def format_unicode_dict(input_dict: dict, remove_unicode: bool) -> dict:
    """
    Format all strings (keys or values) within a dict.

    See: format_unicode_string

    Args:
        input_dict (dict): Dict to be formatted
        remove_unicode (bool): If unicode should be removed

    Returns:
        dict: Formatted dict.
    """
    new_dict = {}
    for key, val in input_dict.items():
        if isinstance(val, dict):
            new_dict[format_unicode_string(key, remove_unicode)] = format_unicode_dict(
                val, remove_unicode
            )
        else:
            new_dict[format_unicode_string(key, remove_unicode)] = format_unicode_string(
                val, remove_unicode
            )
    return new_dict


def transform_event(mappings: tuple, raw_event: dict) -> dict:
    """
    Transform an event dict using the mappings provided.

    Args:
        mappings (tuple): Tuple containing mapping tuples for each event field.
        raw_event (dict): Unprocessed event dict.

    Raises:
        ValueError: If a provided field mapping is not supported.

    Returns:
        dict: Transformed event dict.
    """
    flat_event = flatten_event(
        raw_event,
        use_match_limit=True,
        remove_unicode=False,
        parent_key="",
        sep=".",
    )
    transformed_event = {}
    for mapping in mappings:
        mapping_type = len(mapping)
        field_name = mapping[0]
        extract_lambda = MAPPING_TYPES.get(mapping_type, None)
        if extract_lambda is None:
            raise ValueError(f"Unsupported mapping for field: {field_name}")
        if field_name in flat_event:
            newKey, val = extract_lambda(flat_event, *mapping)
            transformed_event[newKey] = val
    return transformed_event


def handle_matches(matches: list, use_limit: bool, remove_unicode: bool) -> list:
    """
    Applies a limit to the number of matches given.

    Args:
        matches (list): Input matches.
        use_limit (bool): Use MATCHES_LIMIT or not.
        remove_unicode (bool): Remove unicode encoding.

    Returns:
        list: list of matches.
    """
    if use_limit:
        new_match_list = []
        match_count = 0
        for match in matches:
            match_count += 1
            if match_count > MAX_MATCHES:
                new_match_list.append({format_unicode_string("match_limit", remove_unicode): True})
                break
            else:
                new_match_list.append(format_unicode_dict(match, remove_unicode))
        return new_match_list
    return matches
