import pytest

from patchwork.steps import PreparePR


@pytest.fixture
def prepare_pr_instance():
    """Prepares a pull request instance with specified modified code files.
    
    Args:
        None
    
    Returns:
        PreparePR: An instance of the PreparePR class initialized with the modified code files data.
    """
    inputs = {
        "modified_code_files": [
            {"path": "file1", "start_line": 1, "end_line": 2, "commit_message": "commit msg"},
            {"path": "file2", "patch_message": "patch msg"},
            {"path": "file1", "start_line": 3, "end_line": 4, "commit_message": "commit msg"},
        ]
    }
    return PreparePR(inputs)


def test_init_required_keys(prepare_pr_instance):
    """Test that the required keys are properly initialized in the instance.
    
    Args:
        prepare_pr_instance (PRClass): An instance of the class being tested, 
                                        which should have the required keys.
    
    Returns:
        None: This function does not return a value; it asserts the expected condition.
    """
    assert prepare_pr_instance.required_keys == {"modified_code_files"}


def test_init_inputs(prepare_pr_instance):
    """Test the initialization of inputs for a pull request instance.
    
    Args:
        prepare_pr_instance (object): An instance of the pull request being tested, which includes a list of modified code files.
    
    Returns:
        None: This function does not return a value; it asserts that the modified_code_files attribute
              of the prepare_pr_instance matches the expected structure and values.
    """
    assert prepare_pr_instance.modified_code_files == [
        {"path": "file1", "start_line": 1, "end_line": 2, "commit_message": "commit msg"},
        {"path": "file2", "patch_message": "patch msg"},
        {"path": "file1", "start_line": 3, "end_line": 4, "commit_message": "commit msg"},
    ]


def test_run(prepare_pr_instance):
    """Tests the run method of the prepare_pr_instance to ensure it returns a result containing the 'pr_body' key.
    
    Args:
        prepare_pr_instance (Instance): An instance of a class used to prepare pull requests.
    
    Returns:
        None: This function does not return any value, but raises an assertion error if the test fails.
    """
    result = prepare_pr_instance.run()
    assert "pr_body" in result
    assert result["pr_body"].startswith(prepare_pr_instance.header)


def test_run_no_modified_files():
    """Tests the behavior of the PreparePR.run() method when there are no modified files.
    
    This test initializes the PreparePR class with an empty modified_code_files input
    and verifies that the pull request body is empty and the status is set to SKIPPED.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {"modified_code_files": []}
    prepare_pr_instance = PreparePR(inputs)
    result = prepare_pr_instance.run()
    assert result["pr_body"] == ""
    assert prepare_pr_instance.status.name == "SKIPPED"


def test_init_missing_required_keys():
    """Tests the behavior of the PreparePR class when it is initialized 
    with a dictionary that is missing required keys.
    
    This test case verifies that attempting to create an instance of 
    PreparePR without the necessary keys raises a ValueError.
    
    Args:
        None
    
    Returns:
        None
    """
    with pytest.raises(ValueError):
        PreparePR({})


def test_run_pr_header_override():
    """Tests the functionality of overriding the pull request header with a custom header.
    
    Args:
        None
    
    Returns:
        None: This method asserts that the pull request body starts with the custom header specified in the inputs.
    """
    inputs = {
        "modified_code_files": [{"path": "file1"}],
        "pr_header": "Custom PR header",
    }
    prepare_pr_instance = PreparePR(inputs)
    result = prepare_pr_instance.run()
    assert result["pr_body"].startswith("Custom PR header")
