from __future__ import annotations

import atexit
import dataclasses
import signal
import tempfile
from pathlib import Path

import tiktoken
from chardet.universaldetector import UniversalDetector
from git import Head, Repo
from typing_extensions import Any, Callable

from patchwork.common.utils.dependency import chromadb
from patchwork.logger import logger
from patchwork.managed_files import HOME_FOLDER

_CLEANUP_FILES: set[Path] = set()


def _cleanup_files():
    """Cleans up specified files by removing them from the filesystem.
    
    Args:
        None
    
    Returns:
        None: This function does not return any value.
    """ 
    for file in _CLEANUP_FILES:
        file.unlink(missing_ok=True)


def _cleanup_handler(prev_handler: Callable):
    """Wraps a previous handler to perform cleanup operations before its execution.
    
    Args:
        prev_handler Callable: The handler function to be wrapped.
    
    Returns:
        Callable: A new function that performs cleanup and then returns the previous handler.
    """
    def inner(*args):
        """Calls the cleanup function and returns the previous handler.
        
        Args:
            *args: List of arguments to be passed to the inner function.
        
        Returns:
            Callable: The previous handler function that was saved prior to cleanup.
        """
        _cleanup_files()
        return prev_handler

    return inner


for sig in [signal.SIGINT, signal.SIGTERM]:
    prev_handler = signal.getsignal(sig)
    signal.signal(sig, _cleanup_handler(prev_handler))

atexit.register(_cleanup_files)


def defered_temp_file(
    mode="w+b", buffering=-1, encoding=None, newline=None, suffix=None, prefix=None, dir=None, *, errors=None
):
    """Creates a deferred temporary file using the NamedTemporaryFile method.
    
    Args:
        mode str: The mode in which the file is opened (default is "w+b").
        buffering int: The buffering policy used (default is -1, which means the default buffering).
        encoding str or None: The encoding to use for the file (default is None).
        newline str or None: The newline character(s) used in the file (default is None).
        suffix str or None: The suffix to be appended to the file name (default is None).
        prefix str or None: The prefix to be prepended to the file name (default is None).
        dir str or None: The directory where the temporary file will be created (default is None).
        errors str or None: The error handling scheme (default is None). This is a keyword-only argument.
    
    Returns:
        NamedTemporaryFile: A file object that can be used as a temporary file.
    """
    tempfile_fp = tempfile.NamedTemporaryFile(
        mode=mode,
        buffering=buffering,
        encoding=encoding,
        newline=newline,
        suffix=suffix,
        prefix=prefix,
        dir=dir,
        errors=errors,
        delete=False,
    )

    _CLEANUP_FILES.add(Path(tempfile_fp.name))
    return tempfile_fp


def open_with_chardet(file, mode="r", buffering=-1, errors=None, newline=None, closefd=True, opener=None):
    """Opens a file with automatic character encoding detection using chardet.
    
    Args:
        file (str): The path to the file to be opened.
        mode (str): The mode in which to open the file (default is "r").
        buffering (int): The buffering policy (default is -1 which means using the default buffering).
        errors (str): Specifies how errors are to be handled (default is None).
        newline (str): Controls how universal newlines work (default is None).
        closefd (bool): If False and a file is passed, the underlying file descriptor will be kept open when the file is closed (default is True).
        opener (callable): A custom opener; must return an open file object (default is None).
    
    Returns:
        file object: A file object opened with the detected encoding.
    """
    detector = UniversalDetector()
    with open(
        file=file, mode="rb", buffering=buffering, errors=errors, newline=newline, closefd=closefd, opener=opener
    ) as f:
        while True:
            line = f.read(1024)
            if not line:
                break
            detector.feed(line)
            if detector.done:
                break

    detector.close()

    encoding = detector.result.get("encoding", "utf-8")
    return open(
        file=file,
        mode=mode,
        buffering=buffering,
        encoding=encoding,
        errors=errors,
        newline=newline,
        closefd=closefd,
        opener=opener,
    )


_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_openai_tokens(code: str):
    """Counts the number of OpenAI tokens in the given code string.
    
    Args:
        code str: A string of code for which to count tokens.
    
    Returns:
        int: The number of tokens encoded from the input string.
    """
    return len(_ENCODING.encode(code))


def get_vector_db_path() -> str:
    """Retrieves the file path to the Chroma database.
    
    This function constructs the path to the Chroma database located in the user's home folder. If the constructed path is valid, it returns the path as a string. If not, it returns a default path for the database.
    
    Args:
        None
    
    Returns:
        str: The file path to the Chroma database as a string.
    """
    CHROMA_DB_PATH = HOME_FOLDER / "chroma.db"
    if CHROMA_DB_PATH:
        return str(CHROMA_DB_PATH)
    else:
        return ".chroma.db"


def openai_embedding_model(
    inputs: dict,
) -> "chromadb.api.types.EmbeddingFunction"["chromadb.api.types.Documents"] | None:
    """Creates an OpenAI embedding model based on the provided inputs dictionary.
    
    Args:
        inputs dict: A dictionary containing the model name and OpenAI API key.
    
    Returns:
        chromadb.api.types.EmbeddingFunction | None: An OpenAIEmbeddingFunction instance configured with the provided API key and model name, or None if the model name is not specified.
    """
    model = inputs.get(openai_embedding_model.__name__)
    if model is None:
        return None

    api_key = inputs.get("openai_api_key")
    if api_key is None:
        raise ValueError("Missing required input data: 'openai_api_key'")

    return chromadb().utils.embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=model,
    )


def huggingface_embedding_model(
    inputs: dict,
) -> "chromadb.api.types.EmbeddingFunction"["chromadb.api.types.Documents"] | None:
    """Creates and returns a Hugging Face embedding model function based on the provided inputs.
    
    Args:
        inputs dict: A dictionary containing the necessary parameters. 
            It must include the model name under the key of the function name and one of the API keys ('openai_api_key' or 'huggingface_api_key').
    
    Returns:
        chromadb.api.types.EmbeddingFunction | None: An embedding function configured with the specified model and API key, or None if no model is specified.
    """
    model = inputs.get(huggingface_embedding_model.__name__)
    if model is None:
        return None

    api_key = inputs.get("openai_api_key") or inputs.get("huggingface_api_key")
    if api_key is None:
        raise ValueError("Missing required input data: 'openai_api_key' or 'huggingface_api_key'")

    return chromadb().utils.embedding_functions.HuggingFaceEmbeddingFunction(
        api_key=api_key,
        model_name=model,
    )


_EMBEDDING_FUNCS = [openai_embedding_model, huggingface_embedding_model]

_EMBEDDING_TO_API_KEY_NAME: dict[
    str, Callable[[dict], "chromadb.api.type.EmbeddingFunction"["chromadb.api.types.Documents"] | None]
] = {func.__name__: func for func in _EMBEDDING_FUNCS}


def get_embedding_function(inputs: dict) -> "chromadb.api.types.EmbeddingFunction"["chromadb.api.types.Documents"]:
    """Retrieves an embedding function based on provided input keys.
    
    Args:
        inputs dict: A dictionary containing input keys that correspond to 
                     available embedding functions.
    
    Returns:
        chromadb.api.types.EmbeddingFunction: The embedding function that is 
                                                selected based on the input keys.
    """
    embedding_function = next(
        (func(inputs) for input_key, func in _EMBEDDING_TO_API_KEY_NAME.items() if input_key in inputs.keys()),
        chromadb().utils.embedding_functions.SentenceTransformerEmbeddingFunction(),
    )
    if embedding_function is None:
        raise ValueError(f"Missing required input data: one of {_EMBEDDING_TO_API_KEY_NAME.keys()}")

    return embedding_function


def get_current_branch(repo: Repo) -> Head:
    """Retrieve the current branch of a given Git repository.
    
    Args:
        repo Repo: The repository from which to get the current branch.
    
    Returns:
        Head: The current branch of the repository.
    
    Raises:
        ValueError: If the repository is in a detached HEAD state with additional commits, preventing determination of the current branch.
    """ 
    remote = repo.remote("origin")
    if repo.head.is_detached:
        from_branch = next(
            (branch for branch in remote.refs if branch.commit == repo.head.commit and branch.remote_head != "HEAD"),
            None,
        )
    else:
        from_branch = repo.active_branch

    if from_branch is None:
        raise ValueError(
            "Could not determine the current branch."
            "Make sure repository is not in a detached HEAD state with additional commits."
        )

    return from_branch


def is_container() -> bool:
    """Determines whether the current environment is running within a container.
    
    This function checks for the presence of specific files commonly associated with containerized environments,
    as well as examines the cgroup information to ascertain if the process is within a container.
    
    Returns:
        bool: True if the environment is identified as a container, False otherwise.
    """
    test_files = ["/.dockerenv", "/run/.containerenv"]
    if any(Path(file).exists() for file in test_files):
        return True

    cgroup_v1 = Path("/proc/self/cgroup")
    if cgroup_v1.exists():
        with cgroup_v1.open() as f:
            lines = f.readlines()
            for line in lines:
                # format is `hierachy_id:controllers:pathname`
                # cgroup v2 is `0::/`
                hierachy_id, _, rest = line.partition(":")
                controllers, _, pathname = rest.partition(":")
                if hierachy_id != "0" and len(controllers) > 0:
                    return True

    # TODO: cgroup v2 detection
    return False


def exclude_none_dict(d: dict) -> dict:
    """Remove all key-value pairs from a dictionary where the values are None.
    
    Args:
        d dict: The input dictionary from which None values should be excluded.
    
    Returns:
        dict: A new dictionary containing only the key-value pairs where the values are not None.
    """
    return {k: v for k, v in d.items() if v is not None}


@dataclasses.dataclass
class RetryData:
    retry_limit: int
    retry_count: int


def retry(callback: Callable[[RetryData], Any], retry_limit=3) -> Any:
    """Executes a callback function with retries up to a specified limit. If the callback raises an exception, it will automatically retry until the limit is reached.
    
    Args:
        callback Callable[[RetryData], Any]: A function that takes a RetryData object and returns any result.
        retry_limit int: The maximum number of retries allowed (default is 3).
    
    Returns:
        Any: The result of the callback function if successful, otherwise raises the last encountered exception.
    """
    for i in range(retry_limit):
        retry_count = i + 1
        try:
            return callback(RetryData(retry_limit=retry_limit, retry_count=retry_count))
        except Exception as e:
            logger.error(f"Retry {retry_count} failed with error: {e}")
            if retry_count == retry_limit:
                raise e
