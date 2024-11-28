import pytest

from patchwork.steps.ExtractModelResponse.ExtractModelResponse import (
    ExtractModelResponse,
)


@pytest.fixture
def sample_inputs():
    """Returns a sample set of input data for testing purposes.
    
    Args:
        None
    
    Returns:
        dict: A dictionary containing sample OpenAI responses and their corresponding response partitions.
    """
    return {
        "openai_responses": ["partition1response1partition2", "response2partition3"],
        "response_partitions": {"key1": ["partition1", "partition2"], "key2": ["partition3"]},
    }


def test_init_required_keys(sample_inputs):
    """Test the initialization of the ExtractModelResponse class with required keys.
    
    Args:
        sample_inputs dict: A dictionary containing sample input values for initializing the ExtractModelResponse.
    
    Returns:
        None: This function performs assertions and does not return any value.
    """
    step = ExtractModelResponse(sample_inputs)
    assert step.openai_responses == sample_inputs["openai_responses"]
    assert step.partitions == sample_inputs["response_partitions"]


def test_init_missing_required_keys():
    """Test case to verify that a ValueError is raised when required keys are missing 
    during the initialization of the ExtractModelResponse class.
    
    Args:
        None
    
    Returns:
        None
    """
    with pytest.raises(ValueError):
        ExtractModelResponse({})


def test_run_no_partitions(sample_inputs):
    """Test the run method of ExtractModelResponse when no partitions are provided.
    
    Args:
        sample_inputs dict: A dictionary containing sample input data used for testing.
    
    Returns:
        None: This function does not return a value; it asserts conditions on the output.
    """
    step = ExtractModelResponse({**sample_inputs, "response_partitions": {}})
    output = step.run()
    assert len(output["extracted_responses"]) == 2
    assert output["extracted_responses"][0]["anyKeyHere"] == "partition1response1partition2"
    assert output["extracted_responses"][1]["kEy"] == "response2partition3"


def test_run_with_partitions(sample_inputs):
    """Test the `run` method of the `ExtractModelResponse` class with sample inputs.
    
    Args:
        sample_inputs (dict): A dictionary containing the sample input data required for testing.
    
    Returns:
        None: This function does not return a value but asserts the correctness of the output.
    """
    step = ExtractModelResponse(sample_inputs)
    output = step.run()
    assert len(output["extracted_responses"]) == 2
    assert output["extracted_responses"][0]["key1"] == "response1"
    assert output["extracted_responses"][1]["key2"] == "response2"
