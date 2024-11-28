import pytest

from patchwork.steps.GenerateEmbeddings.GenerateEmbeddings import (
    GenerateEmbeddings,
    filter_by_extension,
)


def test_filter_by_extension(tmp_path):
    """Test the filter_by_extension function to verify its behavior when provided with file names and a list of extensions.
    
    Args:
        tmp_path (Path): A temporary directory path provided by pytest for storing temporary files.
    
    Returns:
        None: This function asserts conditions and does not return any values.
    """
    assert filter_by_extension("example.txt", [".txt"])
    assert not filter_by_extension("example.txt", [".pdf"])


def test_generate_embeddings_init():
    """Tests the initialization of the GenerateEmbeddings class.
    
    This function creates a test instance of the GenerateEmbeddings class with given inputs
    and verifies that the collection is initialized and the documents are correctly set.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {"embedding_name": "test", "documents": [{"document": "test document"}]}
    step = GenerateEmbeddings(inputs)
    assert step.collection is not None
    assert step.documents == inputs["documents"]


def test_generate_embeddings_run():
    """Test the execution of the GenerateEmbeddings step.
    
    This function sets up a test case for the GenerateEmbeddings class by providing
    a sample input containing an embedding name and a document. It then runs the
    embedding generation process and asserts that the result is as expected.
    
    Args:
        None
    
    Returns:
        None: This function does not return a value but asserts the correctness of 
        the GenerateEmbeddings run result.
    """
    inputs = {"embedding_name": "test", "documents": [{"document": "test document"}]}
    step = GenerateEmbeddings(inputs)
    result = step.run()
    assert result == {}


def test_generate_embeddings_init_required_keys_missing():
    """Tests the initialization of the GenerateEmbeddings class when required keys are missing from the input.
    
    This test checks if a ValueError is raised when the inputs dictionary does not contain the necessary keys 
    for creating an instance of the GenerateEmbeddings class.
    
    Args:
        inputs dict: A dictionary containing input data, which is expected to have specific keys for initialization.
    
    Returns:
        None: This test does not return any value; it asserts the expected exception behavior.
    """
    inputs = {"documents": [{"document": "test document"}]}
    with pytest.raises(ValueError):
        GenerateEmbeddings(inputs)


def test_generate_embeddings_init_embedding_name_missing():
    """Test the initialization of the GenerateEmbeddings class when the embedding_name parameter is missing.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {"embedding_name": "test"}
    with pytest.raises(ValueError):
        GenerateEmbeddings(inputs)


def test_generate_embeddings_run():
    """Tests the functionality of the GenerateEmbeddings class's run method.
    
    This function initializes the GenerateEmbeddings class with predefined inputs and checks
    if the output of the run method is as expected.
    
    Args:
        inputs dict: A dictionary containing parameters for the embedding generation, 
                      including 'embedding_name' and 'documents'.
    
    Returns:
        None: This function does not return a value. It asserts that the result of the 
              run method is an empty dictionary.
    """
    inputs = {"embedding_name": "test", "documents": [{"document": "test document"}]}
    step = GenerateEmbeddings(inputs)
    result = step.run()
    assert result == {}
