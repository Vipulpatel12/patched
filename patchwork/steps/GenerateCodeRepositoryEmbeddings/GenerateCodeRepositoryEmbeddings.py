from __future__ import annotations

import hashlib
import time
from itertools import islice
from pathlib import Path

import git
from typing_extensions import Iterable

from patchwork.common.utils.dependency import chromadb
from patchwork.common.utils.utils import get_vector_db_path, open_with_chardet
from patchwork.logger import logger
from patchwork.step import Step
from patchwork.steps.GenerateCodeRepositoryEmbeddings.filter_lists import (
    _DIRECTORY_BLACKLIST,
    _EXTENSION_WHITELIST,
)
from patchwork.steps.GenerateEmbeddings.GenerateEmbeddings import GenerateEmbeddings


def filter_files(files: Iterable[str]) -> set[str]:
    """Filters a list of file paths to exclude those containing directories from a blacklist.
    
    Args:
        files Iterable[str]: An iterable collection of file paths as strings to be filtered.
    
    Returns:
        set[str]: A set of file paths that do not contain any directories from the blacklist.
    """
    rv = set()
    for file in files:
        file_path = Path(file)
        if any(directory in file_path.parts for directory in _DIRECTORY_BLACKLIST):
            continue
        rv.add(file)

    return rv


def batch(iterable, n=1):
    """Yield successive n-sized chunks from an iterable.
    
    Args:
        iterable Iterable: An iterable (e.g. list, tuple, etc.) to be divided into chunks.
        n int: The size of each chunk. Defaults to 1.
    
    Returns:
        Iterator: An iterator that yields n-sized chunks from the iterable.
    """
    l = len(iterable)
    for ndx in range(0, l, n):
        yield islice(iterable, ndx, min(ndx + n, l))


def hash_text(text: str | list[str]) -> str:
    """Generates a SHA-256 hash of the given text or concatenated list of strings.
    
    Args:
        text (str | list[str]): The input text as a string or a list of strings to be hashed.
    
    Returns:
        str: The hexadecimal representation of the SHA-256 hash of the input text.
    """
    full_text = text if isinstance(text, str) else "".join(text)
    return hashlib.sha256(full_text.encode()).hexdigest()


class GenerateCodeRepositoryEmbeddings(Step):
    required_keys = {}

    def __init__(self, inputs: dict):
        """Initializes the class with the provided inputs.
        
        Args:
            inputs dict: A dictionary containing the necessary initialization parameters.
                It must include all the required keys specified in `self.required_keys`.
        
        Raises:
            ValueError: If any of the required keys are missing from the inputs dictionary.
        
        Returns:
            None
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.client = chromadb().PersistentClient(path=get_vector_db_path())
        self.disable_cache = inputs.get("disable_cache", False)
        self.inputs = inputs

    def run(self) -> dict:
        """Runs the embedding generation process for files in the current working directory.
        
        This method locates relevant files based on specific extensions, extracts their content, 
        and creates embeddings. It also handles version control integration by appending the current 
        git commit hash to the embedding name and manages cached documents by interacting 
        with an external collection client.
        
        Args:
            self: The instance of the class containing this method.
        
        Returns:
            dict: A dictionary containing the updated inputs, including the embedding name and generated documents.
        """
        cwd = Path.cwd()
        base_embedding_name = cwd.name
        embedding_name = base_embedding_name

        files = set()
        for ext in _EXTENSION_WHITELIST:
            found_files = {str(file.relative_to(cwd)) for file in cwd.glob(f"**/*{ext}")}
            found_files = filter_files(found_files)
            files.update(found_files)

        try:
            repo = git.Repo(cwd, search_parent_directories=True)
            base_embedding_name = Path(repo.working_dir).name
            commit_hash = repo.head.reference.commit.hexsha
            embedding_name = f"{base_embedding_name}_{commit_hash}"

            ignored_files = set()
            for batched_files in batch(files, 10):
                ignored_files.update(repo.ignored(*batched_files))
            files = files - ignored_files
        except git.InvalidGitRepositoryError:
            pass

        reference_collection = None
        is_exact_collection = False
        try:
            reference_collection = self.client.get_collection(embedding_name)
            is_exact_collection = True
        except ValueError as e:
            for collection in self.client.list_collections():
                if not collection.name.startswith(base_embedding_name):
                    continue
                reference_collection = collection
                break

        documents = []
        found_reference_ids = set()
        for file in files:
            try:
                with open_with_chardet(file, "r") as fp:
                    text = fp.read()
            except Exception as e:
                logger.warning(f"Error reading file {file}: {e}")

            if len(text.strip()) == 0:
                continue

            text_hash = hash_text(text)

            documents_to_add = [
                dict(
                    id=file,
                    document=text,
                    hash=text_hash,
                    created_at=int(time.time()),
                    path=file,
                )
            ]
            if reference_collection is not None and not self.disable_cache:
                result = reference_collection.get(
                    where={"$and": [{"hash": text_hash}, {"path": file}]}, include=["metadatas", "embeddings"]
                )
                if len(result["ids"]) > 0:
                    documents_to_add = []
                    for embedding_id, embedding, metadata in zip(
                        result["ids"], result["embeddings"], result["metadatas"]
                    ):
                        original_metadata = {
                            key: value for key, value in metadata.items() if key not in ["id", "embedding"]
                        }
                        original_metadata["path"] = file
                        found_reference_ids.add(embedding_id)
                        documents_to_add.append(dict(id=embedding_id, embedding=embedding, **original_metadata))

            documents.extend(documents_to_add)

        if is_exact_collection and reference_collection is not None and len(found_reference_ids) > 0:
            unused_ids = set(reference_collection.get(include=[])["ids"]) - found_reference_ids
            if len(unused_ids) > 0:
                reference_collection.delete(ids=list(unused_ids))

        self.inputs.update(dict(embedding_name=embedding_name, documents=documents))
        outputs = GenerateEmbeddings(self.inputs).run()
        self.inputs.update(outputs)
        return self.inputs
