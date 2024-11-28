from __future__ import annotations

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    completion_create_params,
)
from typing_extensions import Any, Dict, Iterable, List, Optional, Protocol, Union


class NotGiven:
    ...

    @staticmethod
    def remove_not_given(obj: Any) -> Any:
        """Removes instances of NotGiven from the provided object, which can be a dictionary, list, or any other type.
        
        Args:
            obj Any: The object to be processed, which may contain NotGiven instances.
        
        Returns:
            Any: A new object with NotGiven instances removed, preserving the original structure.
        """
        if isinstance(obj, NotGiven):
            return None
        if isinstance(obj, dict):
            return {k: NotGiven.remove_not_given(v) for k, v in obj.items() if v is not NOT_GIVEN}
        if isinstance(obj, list):
            return [NotGiven.remove_not_given(v) for v in obj if v is not NOT_GIVEN]
        return obj


NOT_GIVEN = NotGiven()


class LlmClient(Protocol):
    def get_models(self) -> set[str]:
        """Retrieve a set of models.
        
        Args:
            None
        
        Returns:
            set[str]: A set containing model names as strings.
        """
        ...

    def is_model_supported(self, model: str) -> bool:
        """Checks whether the specified model is supported by the system.
        
        Args:
            model str: The name of the model to check for support.
        
        Returns:
            bool: True if the model is supported, False otherwise.
        """ 
        ...

    def is_prompt_supported(self, messages: Iterable[ChatCompletionMessageParam], model: str) -> int:
        """Determines if the provided prompt messages are supported by the given model.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of messages to be checked for compatibility with the model.
            model str: The identifier of the model for which the support is being verified.
        
        Returns:
            int: An integer representing the support status of the prompt; typically, 1 for supported and 0 for not supported.
        """
        ...

    def truncate_messages(
        self, messages: Iterable[ChatCompletionMessageParam], model: str
    ) -> Iterable[ChatCompletionMessageParam]:
        """Truncates a list of chat messages to ensure they fit within the specified model constraints.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable collection of chat messages to be truncated.
            model str: The identifier of the model being used, which dictates the truncation rules.
        
        Returns:
            Iterable[ChatCompletionMessageParam]: An iterable collection of truncated chat messages.
        """
        ...

    @staticmethod
    def _truncate_messages(
        client: "LlmClient", messages: Iterable[ChatCompletionMessageParam], model: str
    ) -> Iterable[ChatCompletionMessageParam]:
        """Truncates a list of chat messages to ensure they remain within the supported prompt length for a given model.
        
        Args:
            client (LlmClient): An instance of LlmClient used to check prompt support.
            messages (Iterable[ChatCompletionMessageParam]): An iterable collection of chat messages to be truncated.
            model (str): The identifier of the model for which the message length is being evaluated.
        
        Returns:
            Iterable[ChatCompletionMessageParam]: A truncated iterable of chat messages that adhere to the prompt size limitations.
        """
        safety_margin = 500

        last_message = None
        truncated_messages = []
        for message in messages:
            future_truncated_messages = truncated_messages.copy()
            future_truncated_messages.append(message)
            if client.is_prompt_supported(future_truncated_messages, model) - safety_margin < 0:
                last_message = message
                break
            truncated_messages.append(message)

        if last_message is not None:

            def direction_callback(message_to_test: str) -> int:
                current_messages = truncated_messages.copy()
                current_messages.append({"content": message_to_test})
                # add 500 as a safety margin
                return client.is_prompt_supported(current_messages, model) - safety_margin

            last_message["content"] = LlmClient.__truncate_message(
                message=last_message["content"],
                direction_callback=direction_callback,
                min_guess=1,
                max_guess=len(last_message["content"]),
            )
            truncated_messages.append(last_message)

        return truncated_messages

    @staticmethod
    def __truncate_message(message, direction_callback, min_guess, max_guess):
        # TODO: Add tests for truncate_message
        # if __name__ == "__main__":
        # import random
        # import string
        # for i in range(1, 1000):
        #     text = "".join(random.choices(string.ascii_lowercase, k=random.choice(range(i, i + 20))))
        #     print(f"Truncating {text} to {text[:i]}")
        #     new = truncate_message(text, lambda x: i - len(x))
        #     assert text[:i] == new
        #     print(f"Truncated {text} to {new}")
        """Recursively truncates a message based on a directional feedback callback, adjusting the truncation limits.
        
        Args:
            message (str): The message string to be truncated.
            direction_callback (callable): A callback function that returns an integer indicating the direction of truncation.
            min_guess (int): The minimum index to start truncation from.
            max_guess (int): The maximum index to end truncation at.
        
        Returns:
            str: The truncated message based on the feedback provided by the direction_callback.
        """
        change = int((max_guess - min_guess) / 2)
        guess = min_guess + change
        vector = direction_callback(message[:guess])
        if vector == 0:
            return message[:guess]

        if vector > 0:
            min_guess = guess
        else:
            max_guess = guess

        return LlmClient.__truncate_message(message, direction_callback, min_guess, max_guess)

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
        response_format: str | completion_create_params.ResponseFormat | NotGiven = NOT_GIVEN,
        stop: Union[Optional[str], List[str]] | NotGiven = NOT_GIVEN,
        temperature: Optional[float] | NotGiven = NOT_GIVEN,
        top_logprobs: Optional[int] | NotGiven = NOT_GIVEN,
        top_p: Optional[float] | NotGiven = NOT_GIVEN,
    ) -> ChatCompletion:
        """Generates a chat completion response based on the provided messages and model.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of messages for the chat completion.
            model str: The model identifier to use for generating the response.
            frequency_penalty Optional[float] | NotGiven: Penalty for increasing frequency of tokens.
            logit_bias Optional[Dict[str, int]] | NotGiven: Adjustments to the likelihood of specified tokens.
            logprobs Optional[bool] | NotGiven: Whether to include log probabilities of the generated tokens.
            max_tokens Optional[int] | NotGiven: Maximum number of tokens to generate in the response.
            n Optional[int] | NotGiven: Number of completions to generate for each prompt.
            presence_penalty Optional[float] | NotGiven: Penalty for generating tokens that appear in the prompt.
            response_format str | completion_create_params.ResponseFormat | NotGiven: Format of the response.
            stop Union[Optional[str], List[str]] | NotGiven: Tokens at which to stop generation.
            temperature Optional[float] | NotGiven: Sampling temperature to control randomness of output.
            top_logprobs Optional[int] | NotGiven: Number of top log probabilities to return.
            top_p Optional[float] | NotGiven: Cumulative probability threshold for nucleus sampling.
        
        Returns:
            ChatCompletion: The chat completion response generated by the model.
        """
        ...
