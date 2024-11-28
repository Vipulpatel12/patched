import uuid

import chromadb
import pytest

from patchwork.common.utils.utils import get_vector_db_path
from patchwork.steps.QueryEmbeddings.QueryEmbeddings import QueryEmbeddings


@pytest.fixture
def setup_collection():
    """Sets up a test collection in the ChromaDB persistent client by creating a collection,
    inserting sample documents, and yielding the collection for use. After use, the collection is deleted.
    
    Returns:
        Collection: The created or retrieved collection containing sample documents.
    """ 
    _TEST_COLLECTION = "test"

    client = chromadb.PersistentClient(path=get_vector_db_path())
    collection = client.get_or_create_collection(_TEST_COLLECTION)
    collection.upsert(
        ids=[str(uuid.uuid1()), str(uuid.uuid1()), str(uuid.uuid1())],
        documents=["text1", "text2", "text3"],
        metadatas=[
            {"original_id": "1", "original_document": "text1"},
            {"original_id": "2", "original_document": "text2"},
            {"original_id": "3", "original_document": "text3"},
        ],
    )
    yield collection
    client.delete_collection(_TEST_COLLECTION)


def test_required_keys(setup_collection):
    # Test that the required keys are checked
    """Test the presence of required keys in the input for the QueryEmbeddings class.
    
    Args:
        setup_collection (CollectionSetup): A fixture that sets up the required collection configuration for testing.
    
    Returns:
        None: This is a test function and does not return any value.
    """
    inputs = {"embedding_name": setup_collection.name, "texts": ["text1", "text2"]}
    query_embeddings = QueryEmbeddings(inputs)


def test_missing_required_key():
    # Test that a ValueError is raised when a required key is missing
    """Test that a ValueError is raised when a required key is missing in the input.
    
    This test function verifies that the QueryEmbeddings class raises a ValueError
    if the required key(s) in the inputs dictionary are missing. In this case,
    the test specifically checks for the absence of required keys.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {"texts": ["text1", "text2"]}
    with pytest.raises(ValueError):
        QueryEmbeddings(inputs)


def test_query_results(setup_collection):
    # Test that the query results are processed correctly
    """Test the functionality of processing query results in the specified collection.
    
    Args:
        setup_collection (Collection): An instance of the collection setup used for the query.
    
    Returns:
        None: This function does not return a value. It asserts the correctness of the query results.
    """
    collection = setup_collection
    inputs = {"embedding_name": collection.name, "texts": ["text1", "text2"]}
    query_embeddings = QueryEmbeddings(inputs)
    results = query_embeddings.run()
    assert isinstance(results, dict)
    assert "embedding_results" in results


@pytest.mark.parametrize("top_k", [1, 2, 3])
def test_top_k(setup_collection, top_k):
    # Test that the token limit is enforced
    """Test the enforcement of the token limit in the QueryEmbeddings functionality.
    
    Args:
        setup_collection (Collection): The collection setup required for the test, which contains the embedding configuration.
        top_k (int): The expected number of top results to be returned by the QueryEmbeddings.
    
    Returns:
        None: This function does not return a value; it asserts the correctness of the token limit.
    """ 
    inputs = {"embedding_name": setup_collection.name, "texts": ["text1"], "top_k": top_k}
    query_embeddings = QueryEmbeddings(inputs)
    results = query_embeddings.run()
    assert len(results["embedding_results"]) == top_k
