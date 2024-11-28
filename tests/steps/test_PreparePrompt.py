import itertools
import json
import tempfile

import pytest

from patchwork.steps import PreparePrompt

_PROMPT_ID = "test"
_PROMPT_FILE_DICT = [
    {
        "id": _PROMPT_ID,
        "prompts": [{"role": "system", "content": "{{test1}}"}, {"role": "user", "content": "{{test2}}"}],
    }
]
_PROMPT_VALUES = [
    {"test1": "value1", "test2": "value2", "test3": "value3"},
    {"test1": "value1", "test2": "value2", "test3": "value3"},
]


@pytest.fixture
def valid_prompt_file():
    """Creates a temporary file containing a JSON representation of a predefined prompt file dictionary.
    
    This function generates a temporary file, writes a JSON dump of the 
    _PROMPT_FILE_DICT to it, and yields the name of the temporary file. 
    The file is created with the intention of being used for input purposes 
    and will not be deleted immediately after usage.
    
    Yields:
        str: The name of the temporary file containing the JSON data.
    
    Raises:
        Exception: If there is an error during file operations or JSON serialization.
    """
    fp = tempfile.NamedTemporaryFile("w", delete=False)
    try:
        json.dump(_PROMPT_FILE_DICT, fp)
        fp.flush()
        yield str(fp.name)
    finally:
        fp.close()


@pytest.fixture
def valid_prompt_values_file():
    """Creates a temporary file that contains valid prompt values in JSON format.
    
    This function writes the contents of the global variable `_PROMPT_VALUES` to a newly created temporary file. The file is opened in write mode and will not be deleted when closed. The file's name is yielded as a string for further use, and the file is automatically closed after exiting the context.
    
    Yields:
        str: The name of the temporary file containing the prompt values in JSON format.
    """
    fp = tempfile.NamedTemporaryFile("w", delete=False)
    try:
        json.dump(_PROMPT_VALUES, fp)
        fp.flush()
        yield str(fp.name)
    finally:
        fp.close()


@pytest.mark.parametrize(
    "keys",
    [
        set(),
        {"prompt_template_file"},
        {"prompt_id"},
        {"prompt_values"},
        {"prompt_value_file"},
        {"prompt_template_file", "prompt_id"},
        {"prompt_template_file", "prompt_values"},
        {"prompt_template_file", "prompt_value_file"},
        {"prompt_id", "prompt_values"},
        {"prompt_id", "prompt_value_file"},
        {"prompt_values", "prompt_value_file"},
        {"prompt_template_file", "prompt_values", "prompt_value_file"},
        # this will pass
        # {"prompt_template_file", "prompt_id", "prompt_values"},
    ],
)
def test_prepare_prompt_required_keys(valid_prompt_file, valid_prompt_values_file, keys):
    """Test the PreparePrompt class to ensure that it raises a ValueError when required keys are missing from the input.
    
    Args:
        valid_prompt_file (str): A valid path to the prompt template file.
        valid_prompt_values_file (str): A valid path to the prompt values file.
        keys (list): A list of keys that are considered required but are intentionally provided as missing.
    
    Returns:
        None: This function does not return a value; it asserts that a ValueError is raised.
    """
    inputs = {
        "prompt_template_file": valid_prompt_file,
        "prompt_id": _PROMPT_ID,
        "prompt_values": _PROMPT_VALUES,
        "prompt_value_file": valid_prompt_values_file,
    }
    bad_inputs = {key: value for key, value in inputs.items() if key in keys}
    with pytest.raises(ValueError):
        PreparePrompt(bad_inputs)


@pytest.mark.parametrize("keys", itertools.combinations(["prompt_template_file", "prompt_value_file", ""], 2))
def test_prepare_prompt_non_existent_files(valid_prompt_file, valid_prompt_values_file, keys):
    """Tests the PreparePrompt functionality when provided with non-existent files.
    
    Args:
        valid_prompt_file (str): A valid file path for the prompt template.
        valid_prompt_values_file (str): A valid file path for the prompt values.
        keys (list): A list of keys to be included in the input dictionary, which will have non-existent file paths assigned.
    
    Returns:
        None: The function does not return a value; it asserts that a ValueError is raised when non-existent files are used.
    """
    inputs = {
        "prompt_template_file": valid_prompt_file,
        "prompt_id": _PROMPT_ID,
        "prompt_value_file": valid_prompt_values_file,
    }
    for key in keys:
        inputs[key] = "non-existing-file.json"

    with pytest.raises(ValueError):
        PreparePrompt(inputs)


@pytest.mark.parametrize("key", ["prompt_values", "prompt_value_file"])
def test_prepare_prompt_prompt_values(valid_prompt_file, valid_prompt_values_file, key):
    """Tests the preparation of a prompt by validating the prompt template and values.
    
    Args:
        valid_prompt_file (str): The path to the valid prompt template file.
        valid_prompt_values_file (str): The path to the valid prompt values file.
        key (str): The key to be removed from the inputs dictionary before preparation.
    
    Returns:
        None: This function performs assertions and does not return a value.
    """
    inputs = {
        "prompt_template_file": valid_prompt_file,
        "prompt_id": _PROMPT_ID,
        "prompt_values": _PROMPT_VALUES,
        "prompt_value_file": valid_prompt_values_file,
    }
    del inputs[key]
    prepare_prompt = PreparePrompt(inputs)
    assert prepare_prompt.prompt_template == _PROMPT_FILE_DICT[0]["prompts"]
    assert prepare_prompt.prompt_values == _PROMPT_VALUES


def test_prepare_prompt_prompts(valid_prompt_file):
    """Tests the functionality of the PreparePrompt class for generating prompts from a given prompt template file.
    
    Args:
        valid_prompt_file str: The path to the valid prompt template file used for creating prompts.
    
    Returns:
        None: This test function does not return any value; it asserts the correctness of the prompt generation.
    """
    inputs = {
        "prompt_template_file": valid_prompt_file,
        "prompt_id": _PROMPT_ID,
        "prompt_values": _PROMPT_VALUES,
    }
    prepare_prompt = PreparePrompt(inputs)
    prompts = prepare_prompt.run()
    assert prompts["prompts"] is not None
    assert len(prompts["prompts"]) == 2
