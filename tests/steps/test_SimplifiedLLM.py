import pytest

from patchwork.step import StepStatus
from patchwork.steps.CallLLM.CallLLM import CallLLM
from patchwork.steps.ExtractModelResponse.ExtractModelResponse import (
    ExtractModelResponse,
)
from patchwork.steps.PreparePrompt.PreparePrompt import PreparePrompt
from patchwork.steps.SimplifiedLLM.SimplifiedLLM import SimplifiedLLM


@pytest.mark.parametrize(
    "inputs",
    [
        {
            "prompt_user": "user",
            "model": "model",
            "openai_api_key": "openai_api_key",
            "json": True,
        },
    ],
)
def test_invalid(inputs):
    """Tests the behavior of the SimplifiedLLM class when provided invalid inputs.
    
    Args:
        inputs (Any): The input data that is expected to cause a ValueError.
    
    Returns:
        None: This function does not return a value but asserts that a ValueError is raised.
    """
    with pytest.raises(ValueError):
        SimplifiedLLM(inputs)


def test_non_json_run(mocker):
    """Test the non-JSON run functionality of the SimplifiedLLM class.
    
    This test verifies the integration of the PreparePrompt, CallLLM, and ExtractModelResponse components 
    within the SimplifiedLLM class when processing inputs and ensures that the expected interactions and 
    parameters are correctly handled.
    
    Args:
        mocker (pytest-mock.MockerFixture): The mock fixture from pytest-mock used to create mock objects 
                                             and patch methods for testing.
    
    Returns:
        None: This function performs assertions and does not return any value.
    """
    inputs = dict(
        prompt_user="user",
        prompt_system="system",
        prompt_values=[{"value": "here"}],
        model="model",
        openai_api_key="openai_api_key",
    )

    mocked_prepare_prompt = mocker.MagicMock()
    mocked_prepare_prompt_class = mocker.patch.object(PreparePrompt, "__new__", return_value=mocked_prepare_prompt)
    mocked_prepare_prompt.status = StepStatus.COMPLETED
    mocked_prepare_prompt.status_message = "COMPLETED"

    mocked_call_llm = mocker.MagicMock()
    mocked_call_llm_class = mocker.patch.object(CallLLM, "__new__", return_value=mocked_call_llm)
    mocked_call_llm.status = StepStatus.COMPLETED
    mocked_call_llm.status_message = "COMPLETED"

    mocked_extract_model_response = mocker.MagicMock()
    mocked_extract_model_response_class = mocker.patch.object(
        ExtractModelResponse, "__new__", return_value=mocked_extract_model_response
    )
    mocked_extract_model_response.status = StepStatus.COMPLETED
    mocked_extract_model_response.status_message = "COMPLETED"

    simplified_llm = SimplifiedLLM(inputs)
    output = simplified_llm.run()

    assert mocked_prepare_prompt.run.called
    assert mocked_call_llm.run.called
    assert mocked_extract_model_response.run.called

    prepare_prompt_inputs = mocked_prepare_prompt_class.call_args[0][1]
    assert prepare_prompt_inputs.get("prompt_template_file") is None
    assert prepare_prompt_inputs.get("prompt_id") is None
    assert len(prepare_prompt_inputs["prompt_template"]) == 2
    assert prepare_prompt_inputs["prompt_values"] == inputs["prompt_values"]

    call_llm_inputs = mocked_call_llm_class.call_args[0][1]
    assert call_llm_inputs["model_response_format"] == {"type": "text"}
    assert call_llm_inputs["prompts"] == mocked_prepare_prompt.run().get()
    assert call_llm_inputs["model"] == inputs["model"]
    assert call_llm_inputs["openai_api_key"] == inputs["openai_api_key"]

    extract_model_response_inputs = mocked_extract_model_response_class.call_args[0][1]
    assert extract_model_response_inputs["openai_responses"] == mocked_call_llm.run().get()


def test_json_run(mocker):
    """Test the functionality of the SimplifiedLLM class when processing inputs in JSON format.
    
    Args:
        mocker (pytest-mock.MockerFixture): The mocker fixture provided by pytest for mocking dependencies and functions.
    
    Returns:
        None: This function does not return any value; it asserts conditions to validate the behavior of the code.
    """
    inputs = dict(
        prompt_user="user",
        prompt_system="system",
        prompt_values=[{"value": "here"}],
        model="model",
        openai_api_key="openai_api_key",
        json=True,
    )

    mocked_prepare_prompt = mocker.MagicMock()
    mocked_prepare_prompt_class = mocker.patch.object(PreparePrompt, "__new__", return_value=mocked_prepare_prompt)
    mocked_prepare_prompt.status = StepStatus.COMPLETED
    mocked_prepare_prompt.status_message = "COMPLETED"

    mocked_call_llm = mocker.MagicMock()
    mocked_call_llm_class = mocker.patch.object(CallLLM, "__new__", return_value=mocked_call_llm)
    mocked_call_llm.status = StepStatus.COMPLETED
    mocked_call_llm.status_message = "COMPLETED"

    mocked_extract_model_response = mocker.MagicMock()
    mocked_extract_model_response_class = mocker.patch.object(
        ExtractModelResponse, "__new__", return_value=mocked_extract_model_response
    )
    mocked_extract_model_response.status = StepStatus.COMPLETED
    mocked_extract_model_response.status_message = "COMPLETED"

    simplified_llm = SimplifiedLLM(inputs)
    output = simplified_llm.run()

    assert mocked_prepare_prompt.run.called
    assert mocked_call_llm.run.called
    assert mocked_extract_model_response.run.not_called

    prepare_prompt_inputs = mocked_prepare_prompt_class.call_args[0][1]
    assert prepare_prompt_inputs.get("prompt_template_file") is None
    assert prepare_prompt_inputs.get("prompt_id") is None
    assert len(prepare_prompt_inputs["prompt_template"]) == 2
    assert prepare_prompt_inputs["prompt_values"] == inputs["prompt_values"]

    call_llm_inputs = mocked_call_llm_class.call_args[0][1]
    assert call_llm_inputs["model_response_format"] == {"type": "json_object"}
    assert call_llm_inputs["prompts"] == mocked_prepare_prompt.run().get()
    assert call_llm_inputs["model"] == inputs["model"]
    assert call_llm_inputs["openai_api_key"] == inputs["openai_api_key"]
