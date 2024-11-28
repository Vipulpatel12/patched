from collections import defaultdict

from patchwork.logger import logger
from patchwork.step import Step, StepStatus


class _GetOverriddenDefaultDict(defaultdict):
    def __init__(self, default_factory):
        """Initializes a new instance of the class with a specified default factory.
        
        Args:
            default_factory callable: A callable that will be used to create a default value.
        
        Returns:
            None: This constructor does not return a value.
        """
        super().__init__(default_factory)

    def get(self, key, default=None):
        """Retrieves the value associated with the given key from the object. 
        If the key is not present, it returns a default value by invoking the 
        __missing__ method.
        
        Args:
            key (Any): The key to look up in the object.
            default (Any, optional): The value to return if the key is not found. 
                                     Defaults to None.
        
        Returns:
            Any: The value associated with the key if found, otherwise the result 
                 of invoking __missing__ with the key.
        """
        return self.__missing__(key) if key not in self else self[key]


class ExtractModelResponse(Step):
    required_keys = {"openai_responses"}

    def __init__(self, inputs: dict):
        """Initializer for the class, which validates required keys in the input dictionary and initializes instance attributes.
        
        Args:
            inputs dict: A dictionary containing initialization data, including 'openai_responses' and optionally 'response_partitions'.
        
        Raises:
            ValueError: If any of the required keys are missing from the inputs dictionary.
        
        Returns:
            None
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.openai_responses = inputs["openai_responses"]
        self.partitions = inputs.get("response_partitions", defaultdict(list))

    def run(self) -> dict:
        """Executes the response extraction process from OpenAI responses. 
        
        If there are no OpenAI responses available, it sets the status to skipped. If no partitions are specified, it defaults to using the entire response for extraction.
        
        Args:
            self: The instance of the class containing the method, which holds the OpenAI responses and other related data.
        
        Returns:
            dict: A dictionary containing the extracted responses from the OpenAI responses.
        """
        if len(self.openai_responses) == 0:
            self.set_status(StepStatus.SKIPPED, "No OpenAI responses to extract from.")
            return dict(extracted_responses=[])

        extracted_response_func = self.response_partitioned_dict
        if len(self.partitions) == 0:
            logger.warn("No partitions specified for model response, will default to using the entire response.")
            extracted_response_func = self.auto_pass_dict

        outputs = []
        for openai_response in self.openai_responses:
            output = extracted_response_func(openai_response)
            outputs.append(output)

        return dict(extracted_responses=outputs)

    def auto_pass_dict(self, openai_response: str) -> dict:
        """Constructs a dictionary with a default value derived from the provided OpenAI response string.
        
        Args:
            openai_response str: The response string from OpenAI to be used as the default value for the dictionary.
        
        Returns:
            dict: A dictionary where the default value for missing keys is set to the provided OpenAI response.
        """
        def default_factory(_=None):
            return openai_response

        return _GetOverriddenDefaultDict(default_factory)

    def response_partitioned_dict(self, openai_response: str) -> dict:
        """Processes the OpenAI API response and partitions it based on predefined keys.
        
        Args:
            openai_response str: The response string from OpenAI API to be processed.
        
        Returns:
            dict: A dictionary where keys correspond to predefined partitions and values are the extracted responses.
        """
        output = {}
        for key, partition in self.partitions.items():
            if len(partition) < 1:
                output[key] = openai_response
                continue

            extracted_response = openai_response
            for part in partition[:-1]:
                _, _, extracted_response = extracted_response.partition(part)

            if partition[-1] != "":
                extracted_response, _, _ = extracted_response.partition(partition[-1])

            if extracted_response == "":
                continue

            output[key] = extracted_response
        return output
