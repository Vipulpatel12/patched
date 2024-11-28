import pytest

from patchwork.common.utils.step_typing import (
    StepTypeConfig,
    validate_step_type_config_with_inputs,
    validate_steps_with_inputs,
)
from patchwork.steps import JoinList, ScanSemgrep


def test_valid_input_keys():
    """Test the validation of input keys for the given scanning method.
    
    Args:
        keys set: A set of strings representing the input keys to be validated.
        ScanSemgrep type: A scanning method that will be used alongside the input keys for validation.
    
    Returns:
        None: This function does not return a value; it will raise an error if validation fails.
    """
    keys = {"key1", "key2", "key3"}
    # should not raise any error
    validate_steps_with_inputs(keys, ScanSemgrep)


def test_invalid_input_keys():
    """Tests the behavior of the `validate_steps_with_inputs` function when provided with invalid input keys.
    
    This test checks that a ValueError is raised when the required input data for the steps is missing. It verifies the error message for correctness, ensuring that it lists all missing inputs for each step.
    
    Args:
        None
    
    Returns:
        None
    """
    keys = {"key1", "key2"}
    steps = [JoinList]

    with pytest.raises(ValueError) as exc_info:
        validate_steps_with_inputs(keys, *steps)

    # Ensure the error message is correct
    lines = """\
Invalid inputs for steps:
Step: JoinList
  - delimiter: 
      Missing required input data
  - list: 
      Missing required input data
""".splitlines()

    for line in lines:
        assert line in exc_info.value.args[0]


@pytest.mark.parametrize(
    "key_name, input_keys, step_type_config, expected",
    [
        [
            "key1",
            set(),
            StepTypeConfig(or_op=["key1", "key2", "key3"]),
            (False, "Missing required input: At least one of key1, key1, key2, key3 has to be set"),
        ],
        ["key1", {"key1"}, StepTypeConfig(or_op=["key1", "key2", "key3"]), (True, "")],
        ["key1", {"key2", "key3"}, StepTypeConfig(or_op=["key1", "key2", "key3"]), (True, "")],
        ["key1", {"key1", "key2", "key3"}, StepTypeConfig(and_op=["key1", "key2", "key3"]), (True, "")],
        ["key1", {"key2", "key3"}, StepTypeConfig(and_op=["key1", "key2", "key3"]), (True, "")],
        [
            "key1",
            {"key1", "key3"},
            StepTypeConfig(and_op=["key1", "key2", "key3"]),
            (False, "Missing required input data because key1 is set: key2"),
        ],
        ["key1", {"key1"}, StepTypeConfig(xor_op=["key1", "key2", "key3"]), (True, "")],
        ["key1", {"key2", "key3"}, StepTypeConfig(xor_op=["key1", "key2", "key3"]), (True, "")],
        [
            "key1",
            {"key1", "key3"},
            StepTypeConfig(xor_op=["key1", "key2", "key3"]),
            (False, "Excess input data: key1, key3 cannot be set at the same time"),
        ],
    ],
)
def test_validate_step_type_config(key_name, input_keys, step_type_config, expected):
    """Tests the validation of step type configuration against expected outputs.
    
    Args:
        key_name (str): The name of the key to validate against the configuration.
        input_keys (list): A list of input keys used for the validation.
        step_type_config (dict): A configuration dictionary that defines the step type.
        expected (tuple): A tuple containing the expected boolean result and message.
    
    Returns:
        None: This method does not return a value, but asserts the validation results.
    """
    is_ok, msg = validate_step_type_config_with_inputs(key_name, input_keys, step_type_config)
    assert is_ok == expected[0]
    assert msg == expected[1]
