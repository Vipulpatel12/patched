from __future__ import annotations

import functools
import time

from google import generativeai
from google.generativeai.types.content_types import (
    add_object_type,
    convert_to_nullable,
    strip_titles,
    unpack_defs,
)
from google.generativeai.types.generation_types import GenerateContentResponse
from google.generativeai.types.model_types import Model
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    completion_create_params,
)
from openai.types.chat.chat_completion import ChatCompletion, Choice
from typing_extensions import Any, Dict, Iterable, List, Optional, Union

from patchwork.common.client.llm.protocol import NOT_GIVEN, LlmClient, NotGiven
from patchwork.common.client.llm.utils import json_schema_to_model


@functools.lru_cache
def _cached_list_model_from_google() -> list[Model]:
    """Fetches a list of models from the Google Generative AI service and returns it as a list.
    
    Returns:
        list[Model]: A list of Model objects retrieved from the generative AI service.
    """
    return list(generativeai.list_models())


class GoogleLlmClient(LlmClient):
    __SAFETY_SETTINGS = [
        dict(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        dict(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        dict(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        dict(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    ]
    __MODEL_PREFIX = "models/"

    def __init__(self, api_key: str):
        """Initializes the class with the provided API key and configures the generative AI with it.
        
        Args:
            api_key str: The API key used for authentication with the generative AI service.
        
        Returns:
            None: This method does not return a value.
        """
        self.__api_key = api_key
        generativeai.configure(api_key=api_key)

    def __get_model_limits(self, model: str) -> int:
        """Retrieves the input token limit for a specified model.
        
        Args:
            model str: The name of the model for which the input token limit is to be retrieved.
        
        Returns:
            int: The input token limit for the specified model, or a default limit of 1,000,000 if the model is not found.
        """
        for model_info in _cached_list_model_from_google():
            if model_info.name == f"{self.__MODEL_PREFIX}{model}":
                return model_info.input_token_limit
        return 1_000_000

    def get_models(self) -> set[str]:
        """Retrieves a set of model names by removing the model prefix from the cached list of models.
        
        Args:
            None
        
        Returns:
            set[str]: A set containing the model names without the model prefix.
        """
        return {model.name.removeprefix(self.__MODEL_PREFIX) for model in _cached_list_model_from_google()}

    def is_model_supported(self, model: str) -> bool:
        """Check if a specified model is supported by the system.
        
        Args:
            model str: The name of the model to be checked for support.
        
        Returns:
            bool: True if the model is supported, False otherwise.
        """
        return model in self.get_models()

    def is_prompt_supported(self, messages: Iterable[ChatCompletionMessageParam], model: str) -> int:
        """Checks if the provided chat prompt is supported by the specified model by calculating the token count and comparing it to the model's limitations.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: A collection of chat messages to be evaluated for token limits.
            model str: The name of the model against which the prompt support is being checked.
        
        Returns:
            int: The difference between the model's token limit and the current token count, or -1 if an error occurs during token counting.
        """
        system, chat = self.__openai_messages_to_google_messages(messages)
        gen_model = generativeai.GenerativeModel(model_name=model, system_instruction=system)
        try:
            token_count = gen_model.count_tokens(chat).total_tokens
        except Exception as e:
            return -1
        model_limit = self.__get_model_limits(model)
        return model_limit - token_count

    def truncate_messages(
        self, messages: Iterable[ChatCompletionMessageParam], model: str
    ) -> Iterable[ChatCompletionMessageParam]:
        """Truncates a collection of chat messages to fit within a specified model's constraints.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable collection of chat messages to be truncated.
            model str: The model identifier used to determine the truncation limits.
        
        Returns:
            Iterable[ChatCompletionMessageParam]: An iterable collection of truncated chat messages.
        """
        return self._truncate_messages(self, messages, model)

    @staticmethod
    def __openai_messages_to_google_messages(
        messages: Iterable[ChatCompletionMessageParam],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Converts OpenAI chat messages into a format suitable for Google messages.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: An iterable of chat messages containing message roles and content.
        
        Returns:
            tuple[str, list[dict[str, Any]]]: A tuple where the first element is the system message content as a string (or None if not present), 
            and the second element is a list of dictionaries representing the user and assistant messages along with their content parts.
        """
        system_content = None
        contents = []
        for message in messages:
            if message.get("role") == "system":
                system_content = message.get("content")
                continue
            role = "model" if message.get("role") == "assistant" else "user"
            parts = [dict(text=message.get("content"))]
            contents.append(dict(role=role, parts=parts))

        return system_content, contents

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
        """Generates chat completions based on the provided messages and model parameters.
        
        Args:
            messages Iterable[ChatCompletionMessageParam]: The input messages for the chat completion.
            model str: The model identifier to use for generating the completion.
            frequency_penalty Optional[float] | NotGiven: Optional penalty to apply based on frequency of tokens.
            logit_bias Optional[Dict[str, int]] | NotGiven: Optional bias to apply to specific tokens in generation.
            logprobs Optional[bool] | NotGiven: Optional flag indicating if log probabilities should be returned.
            max_tokens Optional[int] | NotGiven: Optional maximum number of tokens to generate in the response.
            n Optional[int] | NotGiven: Optional number of completions to generate for the prompt.
            presence_penalty Optional[float] | NotGiven: Optional penalty to apply based on presence of tokens.
            response_format completion_create_params.ResponseFormat | NotGiven: Optional format for the response.
            stop Union[Optional[str], List[str]] | NotGiven: Optional stopping sequences for generation.
            temperature Optional[float] | NotGiven: Optional value controlling randomness of outputs.
            top_logprobs Optional[int] | NotGiven: Optional value for number of top log probabilities to return.
            top_p Optional[float] | NotGiven: Optional cumulative probability threshold for sampling.
        
        Returns:
            ChatCompletion: The generated chat completion response object.
        """
        generation_dict = dict(
            stop_sequences=[stop] if isinstance(stop, str) else stop,
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        is_response_format_given = response_format is not NotGiven and isinstance(response_format, dict)
        is_json_object = is_response_format_given and response_format.get("type") == "json_object"
        is_json_schema = is_response_format_given and response_format.get("type") == "json_schema"
        if is_json_object or is_json_schema:
            generation_dict["response_mime_type"] = "application/json"
        if is_json_schema:
            generation_dict["response_schema"] = self.json_schema_to_google_schema(
                response_format.get("json_schema", {}).get("schema")
            )

        system_content, contents = self.__openai_messages_to_google_messages(messages)

        model_client = generativeai.GenerativeModel(
            model_name=model,
            safety_settings=self.__SAFETY_SETTINGS,
            generation_config=NOT_GIVEN.remove_not_given(generation_dict),
            system_instruction=system_content,
        )
        response = model_client.generate_content(contents=contents)
        return self.__google_response_to_openai_response(response, model)

    @staticmethod
    def __google_response_to_openai_response(google_response: GenerateContentResponse, model: str) -> ChatCompletion:
        """Converts a Google response to an OpenAI response format.
        
        Args:
            google_response GenerateContentResponse: The response object obtained from Google's content generation.
            model str: The model name used for generating content.
        
        Returns:
            ChatCompletion: An OpenAI response object formatted from the Google response.
        """
        choices = []
        for candidate in google_response.candidates:
            # note that instead of system, from openai, its model, from google.
            parts = [part.text or part.inline_data for part in candidate.content.parts]

            # google reasons by index = [FINISH_REASON_UNSPECIFIED, STOP, MAX_TOKENS, SAFETY, RECITATION, OTHER]
            # openai allowed reasons: 'stop', 'length', 'tool_calls', 'content_filter', 'function_call'
            finish_reason_map = {
                2: "length",
                3: "content_filter",
            }

            choice = Choice(
                finish_reason=finish_reason_map.get(candidate.finish_reason, "stop"),
                index=candidate.index,
                message=ChatCompletionMessage(
                    content="\n".join(parts),
                    role="assistant",
                ),
            )
            choices.append(choice)

        completion_usage = CompletionUsage(
            completion_tokens=google_response.usage_metadata.candidates_token_count,
            prompt_tokens=google_response.usage_metadata.prompt_token_count,
            total_tokens=google_response.usage_metadata.total_token_count,
        )

        return ChatCompletion(
            id="-1",
            choices=choices,
            created=int(time.time()),
            model=model,
            object="chat.completion",
            usage=completion_usage,
        )

    @staticmethod
    def json_schema_to_google_schema(json_schema: dict[str, Any] | None) -> dict[str, Any] | None:
        """Converts a JSON schema into a Google schema format.
        
        Args:
            json_schema dict[str, Any] | None: The input JSON schema to be converted. 
                If None, the function returns None.
        
        Returns:
            dict[str, Any] | None: A Google schema representation of the input JSON schema. 
                Returns None if the input JSON schema is None.
        """
        if json_schema is None:
            return None

        model = json_schema_to_model(json_schema)
        parameters = model.model_json_schema()
        defs = parameters.pop("$defs", {})

        for name, value in defs.items():
            unpack_defs(value, defs)
        unpack_defs(parameters, defs)
        convert_to_nullable(parameters)
        add_object_type(parameters)
        strip_titles(parameters)
        return parameters
