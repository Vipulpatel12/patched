from patchwork.common.utils.utils import exclude_none_dict
from patchwork.step import Step
from patchwork.steps.CallLLM.CallLLM import CallLLM
from patchwork.steps.ExtractModelResponse.ExtractModelResponse import (
    ExtractModelResponse,
)
from patchwork.steps.LLM.typed import LLMInputs
from patchwork.steps.PreparePrompt.PreparePrompt import PreparePrompt


class LLM(Step):
    def __init__(self, inputs):
        """Initializes the class and checks for required input keys.
        
        Args:
            inputs dict: A dictionary containing the input data to be validated.
        
        Raises:
            ValueError: If any required keys are missing from the provided input data.
        """
        super().__init__(inputs)
        missing_keys = LLMInputs.__required_keys__.difference(set(inputs.keys()))
        if len(missing_keys) > 0:
            raise ValueError(f'Missing required data: "{missing_keys}"')

        self.inputs = inputs

    def run(self) -> dict:
        """Executes a series of tasks to process prompts and extract responses from a language model.
        
        This method orchestrates the flow from preparing prompts, calling the language model (LLM),
        and extracting responses, ultimately returning a structured dictionary with relevant outputs.
        
        Args:
            self: The instance of the class, which contains the inputs necessary for processing.
        
        Returns:
            dict: A dictionary containing the processed information, including prompts, 
                  responses from the LLM, extracted responses, and token counts.
        """
        prepare_prompt_outputs = PreparePrompt(self.inputs).run()
        call_llm_outputs = CallLLM(
            dict(
                prompts=prepare_prompt_outputs.get("prompts"),
                **self.inputs,
            )
        ).run()
        extract_model_response_outputs = ExtractModelResponse(
            dict(
                openai_responses=call_llm_outputs.get("openai_responses"),
                **self.inputs,
            )
        ).run()
        return exclude_none_dict(
            dict(
                prompts=prepare_prompt_outputs.get("prompts"),
                openai_responses=call_llm_outputs.get("openai_responses"),
                extracted_responses=extract_model_response_outputs.get("extracted_responses"),
                request_tokens=call_llm_outputs.get("request_tokens"),
                response_tokens=call_llm_outputs.get("response_tokens"),
            )
        )
