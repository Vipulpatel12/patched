from __future__ import annotations

import uuid

from typing_extensions import Any

from patchwork.common.utils.dependency import chromadb
from patchwork.common.utils.utils import get_embedding_function, get_vector_db_path
from patchwork.step import Step


def filter_by_extension(file, extensions):
    """Checks if a given file has one of the specified extensions.
    
    Args:
        file (str): The name of the file to be checked.
        extensions (list): A list of file extensions to filter by.
    
    Returns:
        bool: True if the file ends with one of the specified extensions; otherwise, False.
    """
    return any(file.endswith(ext) for ext in extensions)


def split_text(document_text: str, chunk_size: int, overlap: int) -> list[str]:
    """Splits the input text into smaller chunks with specified size and overlap.
    
    Args:
        document_text (str): The text document to be split into chunks.
        chunk_size (int): The desired size of each chunk.
        overlap (int): The number of overlapping characters between consecutive chunks.
    
    Returns:
        list[str]: A list of text chunks resulting from the split operation.
    """
    char_length = len(document_text)
    chunks = []
    for i in range(0, char_length, chunk_size - overlap):
        chunk = "".join(document_text[i : i + chunk_size])
        if chunk == "":
            continue

        chunks.append(chunk)

    return chunks


def delete_collection(client, collection_name):
    """Deletes a specified collection from the client.
    
    Args:
        client (Client): The client instance used to manage collections.
        collection_name (str): The name of the collection to be deleted.
    
    Returns:
        None: This method does not return a value.
    """
    for collection in client.list_collections():
        if collection.name == collection_name:
            client.delete_collection(collection_name)
            break


class GenerateEmbeddings(Step):
    required_keys = {"embedding_name", "documents"}

    def __init__(self, inputs: dict):
        """Initializes an instance of the class with the provided inputs.
        
        Args:
            inputs dict: A dictionary containing the necessary parameters to initialize the instance, including required keys, embedding name, documents, and optional chunk and overlap sizes.
        
        Raises:
            ValueError: If any of the required keys are missing in the provided inputs.
        
        Returns:
            None
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        client = chromadb().PersistentClient(path=get_vector_db_path())

        if inputs.get("disable_cache", False):
            delete_collection(client, inputs["embedding_name"])

        embedding_function = get_embedding_function(inputs)
        self.collection = client.get_or_create_collection(
            inputs["embedding_name"], embedding_function=embedding_function, metadata={"hnsw:space": "cosine"}
        )
        self.documents: list[dict[str, Any]] = inputs["documents"]

        self.chunk_size = inputs.get("chunk_size", 4000)
        self.overlap_size = inputs.get("overlap_size", 2000)

    def run(self) -> dict:
        """Run the processing and upserting of documents and embeddings.
        
        This method extracts text and embeddings from a collection of documents, splits the text into chunks, generates unique IDs for each document chunk and embedding, and then upserts them into a specified collection.
        
        Args:
            self: The instance of the class that holds the documents, chunk size, overlap size, and collection to upsert into.
        
        Returns:
            dict: An empty dictionary indicating the completion of the processing.
        """
        document_ids = []
        documents = []
        document_metadatas = []

        embedding_ids = []
        embeddings = []
        embedding_metadatas = []
        for document in self.documents:
            document_text = document.get("document")
            embedding = document.get("embedding")

            if document_text is not None:
                doc_id = str(document.get("id"))
                document_texts = split_text(document_text, self.chunk_size, self.overlap_size)
                for i, document_text in enumerate(document_texts):
                    document_ids.append(str(uuid.uuid4()))
                    documents.append(document_text)

                    metadata = {key: value for key, value in document.items() if key not in ["id", "document"]}
                    metadata["original_document"] = document_text
                    metadata["original_id"] = doc_id
                    document_metadatas.append(metadata)
            elif embeddings is not None:
                embedding_ids.append(str(document.get("id")))
                embeddings.append(embedding)

                metadata = {key: value for key, value in document.items() if key not in ["embedding"]}
                embedding_metadatas.append(metadata)

        if len(document_ids) > 0:
            self.collection.upsert(ids=document_ids, documents=documents, metadatas=document_metadatas)
        if len(embedding_ids) > 0:
            self.collection.upsert(ids=embedding_ids, embeddings=embeddings, metadatas=embedding_metadatas)

        return dict()
