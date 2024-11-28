import pytest

from patchwork.steps import ReadIssues


@pytest.mark.parametrize(
    "inputs_extra,method_path,issue_texts",
    [
        (
            {"github_api_key": "key"},
            "patchwork.common.client.scm.GithubClient.find_issue_by_url",
            dict(title="", body="github pr body", comments=["nothing", "there"]),
        ),
        (
            {"gitlab_api_key": "key"},
            "patchwork.common.client.scm.GitlabClient.find_issue_by_url",
            dict(title="gitlab pr title", body="", comments=["something", "here"]),
        ),
    ],
)
def test_read_issues(mocker, inputs_extra, method_path, issue_texts):
    # Set up
    """Tests the functionality of the ReadIssues class's run method by mocking the SCM client.
    
    Args:
        mocker: The mocker fixture used for creating mock objects and patching.
        inputs_extra (dict): Additional input parameters to be combined with base inputs.
        method_path (str): The path of the method to be mocked for the SCM client.
        issue_texts (dict): A dictionary containing the expected issue texts returned by the mocked SCM client.
    
    Returns:
        None: This function does not return a value, but will assert the correctness of the ReadIssues run method output.
    """
    base_inputs = {"issue_url": "https://example.com/issue"}
    inputs = {**base_inputs, **inputs_extra}

    mocked_scm_client = mocker.patch(method_path)
    mocked_scm_client.return_value = issue_texts

    # Actual Run
    read_issues = ReadIssues(inputs)
    results = read_issues.run()

    # Assertions
    assert results == {f"issue_{key}": value for key, value in issue_texts.items()}
