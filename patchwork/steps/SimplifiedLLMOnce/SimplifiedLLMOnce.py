from patchwork.step import Step
from patchwork.steps.SimplifiedLLM.SimplifiedLLM import SimplifiedLLM
from patchwork.steps.SimplifiedLLMOnce.typed import SimplifiedLLMOnceInputs


class SimplifiedLLMOnce(Step, input_class=SimplifiedLLMOnceInputs):
    def __init__(self, inputs):
        """Initializes a new instance of the class.
        
        Args:
            inputs dict: A dictionary containing the necessary input parameters:
                - user_prompt (str): The prompt provided by the user.
                - system_prompt (str, optional): The prompt provided by the system.
                - prompt_value (str): The value associated with the prompt.
                - json_schema (dict): A JSON schema for validation or structure purposes.
        
        Returns:
            None: This method does not return any value.
        """
        super().__init__(inputs)

        self.user = inputs["user_prompt"]
        self.system = inputs.get("system_prompt")
        self.prompt_value = inputs["prompt_value"]
        self.json_example = inputs["json_schema"]
        self.inputs = inputs

    def run(self) -> dict:
        """Executes a process to generate a response using a simplified language model (LLM) and returns relevant metrics.
        
        The method constructs a dictionary of prompts based on the provided system and user inputs, then initializes the LLM with the necessary parameters. It retrieves the output from the LLM, set the status based on the LLM's current state, and formats the response to include extracted responses and token counts.
        
        Args:
            self: instance of the class containing the system and user attributes, as well as other necessary inputs.
        
        Returns:
            dict: A dictionary containing the extracted responses, request tokens, and response tokens.
        """
        if self.system is not None:
            prompt_dict = dict(
                prompt_system=self.system,
                prompt_user=self.user,
            )
        else:
            prompt_dict = dict(
                prompt_user=self.user,
            )

        llm = SimplifiedLLM(
            {
                **self.inputs,
                **prompt_dict,
                "prompt_values": [self.prompt_value],
                "json": True,
                "json_example": self.json_example,
            }
        )
        llm_output = llm.run()
        self.set_status(llm.status, llm.status_message)

        return {
            **llm_output.get("extracted_responses")[0],
            "request_tokens": llm_output.get("request_tokens")[0],
            "response_tokens": llm_output.get("response_tokens")[0],
        }
