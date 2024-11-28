from __future__ import annotations

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    completion_create_params,
)
from typing_extensions import Dict, Iterable, List, Optional, Union

from patchwork.common.client.llm.protocol import NOT_GIVEN, LlmClient, NotGiven
from patchwork.logger import logger


class AioLlmClient(LlmClient):
    def __init__(self, *clients: LlmClient):
        """Initializes an instance of the class, accepting a variable number of LlmClient instances.
        
        Args:
            clients LlmClient: One or more instances of LlmClient that will be managed by this class.
        
        Returns:
            None: This method does not return a value but sets up the internal state of the instance.
        """
        self.__original_clients = clients
        self.__clients = []
        self.__supported_models = set()
        for client in clients:
            try:
                self.__supported_models.update(client.get_models())
                self.__clients.append(client)
            except Exception:
                pass

    def get_models(self) -> set[str]:
        """Retrieves the set of supported models.
        
        Args:
            None
        
        Returns:
            set[str]: A set containing the names of the supported models.
        """
        return self.__supported_models

    def is_model_supported(self, model: str) -> bool:
        """Checks if a specified model is supported by any of the clients.
        
        Args:
            model str: The name of the model to check for support.
        
        Returns:
            bool: True if the model is supported by any client, otherwise False.
        """
        return any(client.is_model_supported(model) for client in self.__clients)

    def is_prompt_supported(self, messages: Iterable[ChatCompletionMessageParam], model: str) -> int:
        """Checks if the specified prompt is supported by any of the clients for the given model.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of chat completion message parameters to check support for.
            model str: The model identifier to check against client capabilities.
        
        Returns:
            int: Returns the support level of the prompt for the model, or -1 if no client supports the model.
        """
        for client in self.__clients:
            if client.is_model_supported(model):
                return client.is_prompt_supported(messages, model)
        return -1

    def truncate_messages(
        self, messages: Iterable[ChatCompletionMessageParam], model: str
    ) -> Iterable[ChatCompletionMessageParam]:
        """Truncates a list of chat messages based on model support, using the appropriate client.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable containing chat messages to be truncated.
            model str: The model identifier to check for support in clients.
        
        Returns:
            Iterable[ChatCompletionMessageParam]: An iterable of truncated chat messages if a supported client is found; otherwise, the original messages.
        """
        for client in self.__clients:
            if client.is_model_supported(model):
                return client.truncate_messages(messages, model)
        return messages

    def chat_completion(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        model: str,
        frequency_penalty: Optional[float] | NotGiven = NOT_GIVEN,
        logit_bias: Optional[Dict[str, int]] | NotGiven = NOT_GIVEN,
        logprobs: Optional[bool] | NotGiven = NOT_GIVEN,
        max_tokens: Optional[int] | NotGiven = NOT_GIVEN,
        n: Optional[int] | NotGiven = NOT_GIVEN,
        presence_penalty: Optional[float] | NotGiven = NOT_GIVEN,
        response_format: dict | completion_create_params.ResponseFormat | NotGiven = NOT_GIVEN,
        stop: Union[Optional[str], List[str]] | NotGiven = NOT_GIVEN,
        temperature: Optional[float] | NotGiven = NOT_GIVEN,
        top_logprobs: Optional[int] | NotGiven = NOT_GIVEN,
        top_p: Optional[float] | NotGiven = NOT_GIVEN,
    ) -> ChatCompletion:
        """Generates a chat completion response based on the provided messages and model.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of messages to initiate the chat completion.
            model str: The model identifier to be used for generating the response.
            frequency_penalty Optional[float] | NotGiven: A penalty applied to the frequency of tokens, to reduce repetition.
            logit_bias Optional[Dict[str, int]] | NotGiven: Biases to apply to specific tokens in the output.
            logprobs Optional[bool] | NotGiven: If true, the API will return the log probabilities of each token.
            max_tokens Optional[int] | NotGiven: The maximum number of tokens to generate in the response.
            n Optional[int] | NotGiven: The number of completions to generate for each prompt.
            presence_penalty Optional[float] | NotGiven: A penalty applied to new tokens, to encourage or discourage new topics.
            response_format dict | completion_create_params.ResponseFormat | NotGiven: The format of the response.
            stop Union[Optional[str], List[str]] | NotGiven: One or several stopping sequences where the API will stop generating further tokens.
            temperature Optional[float] | NotGiven: Controls randomness in sampling. Lower values make the output more deterministic.
            top_logprobs Optional[int] | NotGiven: The number of top tokens to consider for sampling.
            top_p Optional[float] | NotGiven: Controls diversity via nucleus sampling; the model considers the results of the tokens with top_p probability mass.
        
        Returns:
            ChatCompletion: The generated chat completion response based on the input messages.
        """
        for client in self.__clients:
            if client.is_model_supported(model):
                logger.debug(f"Using {client.__class__.__name__} for model {model}")
                return client.chat_completion(
                    messages,
                    model,
                    frequency_penalty,
                    logit_bias,
                    logprobs,
                    max_tokens,
                    n,
                    presence_penalty,
                    response_format,
                    stop,
                    temperature,
                    top_logprobs,
                    top_p,
                )
        client_names = [client.__class__.__name__ for client in self.__original_clients]
        raise ValueError(
            f"Model {model} is not supported by {client_names} clients. "
            f"Please ensure that the respective API keys are correct."
        )
