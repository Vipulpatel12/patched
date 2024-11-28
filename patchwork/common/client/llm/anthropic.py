from __future__ import annotations

import json
import time
from functools import lru_cache

from anthropic import Anthropic
from anthropic.types import Message, TextBlockParam
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    completion_create_params,
)
from openai.types.chat.chat_completion import Choice, CompletionUsage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from openai.types.completion_usage import CompletionUsage
from typing_extensions import Dict, Iterable, List, Optional, Union

from patchwork.common.client.llm.protocol import NOT_GIVEN, LlmClient, NotGiven


def _anthropic_to_openai_response(model: str, anthropic_response: Message) -> ChatCompletion:
    """Converts an Anthropics API response into an OpenAI ChatCompletion format.
    
    Args:
        model (str): The model identifier used for generating the response.
        anthropic_response (Message): The response object from the Anthropics API containing message content and usage information.
    
    Returns:
        ChatCompletion: An OpenAI ChatCompletion object that encapsulates the converted response and related metadata.
    """
    stop_reason_map = {"end_turn": "stop", "max_tokens": "length", "stop_sequence": "stop", "tool_use": "tool_calls"}

    choices = []
    for i, content_block in enumerate(anthropic_response.content):
        if content_block.type == "text":
            chat_completion_message = ChatCompletionMessage(
                role="assistant",
                content=content_block.text,
            )
        else:
            text = json.dumps(content_block.input)
            chat_completion_message = ChatCompletionMessage(
                role="assistant",
                content=text,
                tool_calls=[
                    ChatCompletionMessageToolCall(
                        id=content_block.id, type="function", function=Function(name=content_block.name, arguments=text)
                    )
                ],
            )
        choice = Choice(
            index=i,
            finish_reason=stop_reason_map.get(anthropic_response.stop_reason, "stop"),
            message=chat_completion_message,
        )
        choices.append(choice)

    return ChatCompletion(
        id=anthropic_response.id,
        choices=choices,
        created=int(time.time()),
        model=model,
        object="chat.completion",
        usage=CompletionUsage(
            completion_tokens=anthropic_response.usage.output_tokens,
            prompt_tokens=anthropic_response.usage.input_tokens,
            total_tokens=anthropic_response.usage.output_tokens + anthropic_response.usage.input_tokens,
        ),
    )


class AnthropicLlmClient(LlmClient):
    __allowed_model_prefix = "claude-3-"
    __definitely_allowed_models = {"claude-2.0", "claude-2.1", "claude-instant-1.2"}
    __100k_models = {"claude-2.0", "claude-instant-1.2"}

    def __init__(self, api_key: str):
        """Initializes an instance of the class with the provided API key.
        
        Args:
            api_key str: The API key used to authenticate with the Anthropic service.
        
        Returns:
            None: This constructor does not return a value.
        """
        self.client = Anthropic(api_key=api_key)

    def __get_model_limit(self, model: str) -> int:
        # it is observed that the count tokens is not accurate, so we are using a safety margin
        # we usually see 40k tokens overestimation on large prompts
        """Retrieve the maximum token limit for a given model, applying a safety margin to account for overestimation in token counting.
        
        Args:
            model str: The name of the model for which to retrieve the token limit.
        
        Returns:
            int: The adjusted maximum token limit for the specified model, accounting for the safety margin.
        """
        safety_margin = 40_000
        if model in self.__100k_models:
            return 100_000 - safety_margin
        return 200_000 - safety_margin

    @lru_cache(maxsize=None)
    def get_models(self) -> set[str]:
        """Retrieves a set of model names by combining definitely allowed models 
        with the allowed model prefix.
        
        Args:
            None
        
        Returns:
            set[str]: A set of model names including both explicitly allowed models 
            and those that match the allowed model prefix.
        """
        return self.__definitely_allowed_models.union(set(f"{self.__allowed_model_prefix}*"))

    def is_model_supported(self, model: str) -> bool:
        """Checks if the specified model is supported.
        
        Args:
            model str: The name of the model to check for support.
        
        Returns:
            bool: True if the model is supported; otherwise, False.
        """ 
        return model in self.__definitely_allowed_models or model.startswith(self.__allowed_model_prefix)

    def is_prompt_supported(self, messages: Iterable[ChatCompletionMessageParam], model: str) -> int:
        """Checks if the total token count of the provided messages exceeds the model's limit.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable collection of chat completion messages to analyze.
            model str: The identifier of the model to determine its token limit.
        
        Returns:
            int: The remaining token count if within the limit, or -1 if the total exceeds the model's limit.
        """
        model_limit = self.__get_model_limit(model)
        token_count = 0
        for message in messages:
            message_token_count = self.client.count_tokens(message.get("content"))
            token_count = token_count + message_token_count
            if token_count > model_limit:
                return -1

        return model_limit - token_count

    def truncate_messages(
        self, messages: Iterable[ChatCompletionMessageParam], model: str
    ) -> Iterable[ChatCompletionMessageParam]:
        """Truncates a list of chat messages to fit within model constraints.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable containing the chat messages to be truncated.
            model str: The identifier of the model used to determine truncation limits.
        
        Returns:
            Iterable[ChatCompletionMessageParam]: An iterable containing the truncated chat messages.
        """
        return self._truncate_messages(self, messages, model)

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
        response_format: completion_create_params.ResponseFormat | NotGiven = NOT_GIVEN,
        stop: Union[Optional[str], List[str]] | NotGiven = NOT_GIVEN,
        temperature: Optional[float] | NotGiven = NOT_GIVEN,
        top_logprobs: Optional[int] | NotGiven = NOT_GIVEN,
        top_p: Optional[float] | NotGiven = NOT_GIVEN,
    ) -> ChatCompletion:
        """Generates a chat completion response based on the provided messages and model parameters.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of messages to be processed, including system and user messages.
            model str: The model to use for generating the chat completion.
            frequency_penalty Optional[float] | NotGiven: (Optional) A penalty applied to frequency of words.
            logit_bias Optional[Dict[str, int]] | NotGiven: (Optional) A bias applied to specific tokens.
            logprobs Optional[bool] | NotGiven: (Optional) Whether to include log probabilities of the tokens.
            max_tokens Optional[int] | NotGiven: (Optional) The maximum number of tokens to generate in the completion.
            n Optional[int] | NotGiven: (Optional) The number of completions to generate for each prompt.
            presence_penalty Optional[float] | NotGiven: (Optional) A penalty applied to presence of words in the chat.
            response_format completion_create_params.ResponseFormat | NotGiven: (Optional) The format in which to return the response.
            stop Union[Optional[str], List[str]] | NotGiven: (Optional) A stop sequence or sequences where the response generation will halt.
            temperature Optional[float] | NotGiven: (Optional) A sampling temperature to control randomness in the output.
            top_logprobs Optional[int] | NotGiven: (Optional) The number of log probabilities to include for the most likely tokens.
            top_p Optional[float] | NotGiven: (Optional) A value to control diversity through nucleus sampling.
        
        Returns:
            ChatCompletion: The generated chat completion response containing the response text and other related data.
        """
        system: Union[str, Iterable[TextBlockParam]] | NotGiven = NOT_GIVEN
        other_messages = []
        for message in messages:
            if message.get("role") == "system":
                if system is NOT_GIVEN:
                    system = list()
                system.append(TextBlockParam(text=message.get("content"), type="text"))
            else:
                other_messages.append(message)

        default_max_token = 1000
        input_kwargs = dict(
            messages=other_messages,
            system=system,
            max_tokens=default_max_token if max_tokens is None or max_tokens is NOT_GIVEN else max_tokens,
            model=model,
            stop_sequences=[stop] if isinstance(stop, str) else stop,
            temperature=temperature,
            top_p=top_p,
        )
        if response_format is not NOT_GIVEN and response_format.get("type") == "json_schema":
            input_kwargs["tool_choice"] = dict(type="tool", name="response_format")
            input_kwargs["tools"] = [
                dict(
                    name="response_format",
                    description="The response format to use",
                    input_schema=response_format["json_schema"]["schema"],
                )
            ]

        response = self.client.messages.create(**NotGiven.remove_not_given(input_kwargs))
        return _anthropic_to_openai_response(model, response)
