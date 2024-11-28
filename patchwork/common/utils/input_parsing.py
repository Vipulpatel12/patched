from __future__ import annotations

from collections.abc import Iterable, Mapping

from typing_extensions import AnyStr, Union

__ITEM_TYPE = Union[AnyStr, Mapping]


def __parse_to_list_handle_str(input_value: AnyStr, possible_delimiters: Iterable[AnyStr | None]) -> list[str]:
    """Parses the input string into a list based on the provided delimiters.
    
    Args:
        input_value AnyStr: The string input to be parsed into a list.
        possible_delimiters Iterable[AnyStr | None]: An iterable of potential delimiters to split the input string.
    
    Returns:
        list[str]: A list of substrings created by splitting the input string based on the first matching delimiter.
    """
    for possible_delimiter in possible_delimiters:
        if possible_delimiter is None:
            return input_value.split()

        if possible_delimiter in input_value:
            return input_value.split(possible_delimiter)

    return []


def __parse_to_list_handle_dict(input_value: Mapping, possible_keys: Iterable[AnyStr | None]) -> list[str]:
    """Parses the input mapping to a list by checking for possible keys.
    
    Args:
        input_value Mapping: A mapping (e.g., dictionary) to retrieve values from.
        possible_keys Iterable[AnyStr | None]: An iterable of potential keys to search for in the input mapping.
    
    Returns:
        list[str]: A list of strings corresponding to the value of the first found key, or an empty list if no keys are found.
    """
    for possible_key in possible_keys:
        if input_value.get(possible_key) is not None:
            return input_value.get(possible_key)

    return []


def __parse_to_list_handle_iterable(
    input_value: Iterable[__ITEM_TYPE], possible_keys: Iterable[AnyStr | None]
) -> list[str]:
    """Parses an iterable input, extracting values associated with specified keys from dictionaries, 
    or directly appending the items if they are not dictionaries.
    
    Args:
        input_value Iterable[__ITEM_TYPE]: The input iterable containing items to be parsed.
        possible_keys Iterable[AnyStr | None]: A collection of keys to look for in the dictionaries.
    
    Returns:
        list[str]: A list of extracted string values from the input iterable.
    """
    rv = []
    for item in input_value:
        if isinstance(item, dict):
            for possible_key in possible_keys:
                if item.get(possible_key) is not None:
                    rv.append(item.get(possible_key))
        else:
            rv.append(item)

    return rv


def parse_to_list(
    input_value: __ITEM_TYPE | Iterable[__ITEM_TYPE],
    possible_delimiters: Iterable[AnyStr | None] | None = None,
    possible_keys: Iterable[AnyStr | None] | None = None,
) -> list[str]:
    """Parses the input value into a list of strings based on the provided delimiters and keys.
    
    Args:
        input_value (__ITEM_TYPE | Iterable[__ITEM_TYPE]): The value to be parsed, which can be a single item or an iterable collection.
        possible_delimiters (Iterable[AnyStr | None] | None): An optional collection of delimiters to use when parsing strings.
        possible_keys (Iterable[AnyStr | None] | None): An optional collection of keys to use when parsing dictionaries.
    
    Returns:
        list[str]: A list of non-empty strings extracted from the input value.
    """
    if len(input_value) < 1:
        return []

    if possible_delimiters is None:
        possible_delimiters = []
    if possible_keys is None:
        possible_keys = []

    value_to_parse = []
    if isinstance(input_value, dict):
        value_to_parse = __parse_to_list_handle_dict(input_value, possible_keys)
    elif isinstance(input_value, str):
        value_to_parse = __parse_to_list_handle_str(input_value, possible_delimiters)
    elif isinstance(input_value, Iterable):
        value_to_parse = __parse_to_list_handle_iterable(input_value, possible_keys)

    rv = []
    for value in value_to_parse:
        stripped_value = value.strip()
        if stripped_value == "":
            continue
        rv.append(stripped_value)
    return rv
