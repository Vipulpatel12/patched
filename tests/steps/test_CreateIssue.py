import pytest

from patchwork.steps.CreateIssue.CreateIssue import CreateIssue


@pytest.mark.parametrize(
    "inputs",
    [
        {"issue_title": "my issue", "issue_text": "my issue text", "scm_url": "https://github.com/my/repo"},
        {"issue_title": "my issue", "issue_text": "my issue text", "github_api_key": "my api key"},
        {"issue_title": "my issue", "scm_url": "https://github.com/my/repo", "github_api_key": "my api key"},
        {"issue_text": "my issue text", "scm_url": "https://github.com/my/repo", "github_api_key": "my api key"},
    ],
)
def test_init_missing_required_keys(inputs):
    """Test the initialization of the CreateIssue class when required keys are missing.
    
    Args:
        inputs dict: A dictionary of inputs passed to the CreateIssue class.
    
    Returns:
        None: This test checks for the expected exception and does not return a value.
    """
    with pytest.raises(ValueError) as e:
        CreateIssue(inputs)


def test_init_required_keys():
    """Tests the initialization of required keys in the CreateIssue class.
    
    This function verifies that the CreateIssue class initializes its attributes 
    correctly based on the provided input dictionary.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {
        "issue_title": "my issue",
        "issue_text": "my issue text",
        "scm_url": "https://github.com/my/repo",
        "github_api_key": "my api key",
    }
    create_issue = CreateIssue(inputs)
    assert create_issue.issue_title == "my issue"
    assert create_issue.issue_text == "my issue text"


def test_run(mocker):
    """Tests the run method of the CreateIssue class.
    
    This test verifies that the run method correctly creates an issue and returns the associated issue URL.
    It mocks the behavior of the GithubClient's create_issue_comment method to simulate the creation of an issue comment.
    
    Args:
        mocker (mocker.MagicMock): A mock object that allows for patching and testing of dependencies.
    
    Returns:
        None: This function does not return a value as it asserts conditions.
    """
    inputs = {
        "issue_title": "my issue",
        "issue_text": "my issue text",
        "scm_url": "https://github.com/my/repo",
        "github_api_key": "my api key",
    }
    mocked_create_issue_comment = mocker.patch("patchwork.common.client.scm.GithubClient.create_issue_comment")
    mocked_create_issue_comment.return_value = "https://github.com/my/repo/issues/1"

    create_issue = CreateIssue(inputs)
    output = create_issue.run()
    assert output["issue_url"] == "https://github.com/my/repo/issues/1"
    assert create_issue.scm_client is not None
