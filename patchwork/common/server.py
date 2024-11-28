from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import HTTPException
from openai.types.chat import ChatCompletion
from typing_extensions import Annotated

from patchwork.common.client.llm.aio import AioLlmClient
from patchwork.common.client.llm.anthropic import AnthropicLlmClient
from patchwork.common.client.llm.google import GoogleLlmClient
from patchwork.common.client.llm.openai_ import OpenAiLlmClient

app = FastAPI()


@app.post("/v1/chat/completions")
async def handle_openai(
    authorization: Annotated[str, Header()],
    request: Request,
    response: Response,
) -> ChatCompletion:
    """Handles the interaction with various language model clients for chat completion.
    
    This asynchronous function processes a request for chat completion using OpenAI, Google, and Anthropic language models. It begins by extracting the API key from the authorization header, then constructs clients for each language model provider. The function attempts to complete the chat using the given body parameters, handling any exceptions that may arise during the process.
    
    Args:
        authorization str: The authorization header containing the Bearer token for API access.
        request Request: The HTTP request containing the input data for the chat completion.
        response Response: The HTTP response object to send back the completion result.
    
    Returns:
        ChatCompletion: The result of the chat completion from the language model clients.
    
    Raises:
        HTTPException: If an error occurs during the chat completion, it raises an HTTP exception with the appropriate status code and error details.
    """ 
    _, _, api_key = authorization.partition("Bearer ")
    body = await request.json()

    openai_client = OpenAiLlmClient(api_key=api_key)
    google_client = GoogleLlmClient(api_key=api_key)
    anthropic_client = AnthropicLlmClient(api_key=api_key)
    aio_client = AioLlmClient(openai_client, google_client, anthropic_client)
    try:
        return aio_client.chat_completion(**body)
    except Exception as e:
        status_code = getattr(e, "status_code", 500)
        body = getattr(e, "body", {"error_message": str(e)})
        raise HTTPException(status_code=status_code, detail=body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
