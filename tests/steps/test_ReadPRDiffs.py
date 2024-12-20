import pytest

from patchwork.common.client.scm import PullRequestProtocol
from patchwork.steps.ReadPRDiffs.ReadPRDiffs import _IGNORED_EXTENSIONS, ReadPRDiffs


@pytest.mark.parametrize(
    "inputs_extra,method_path,texts,expected",
    [
        (
            {"github_api_key": "key"},
            "patchwork.common.client.scm.GithubClient.get_pr_by_url",
            dict(title="this", body="", comments=[], diffs=dict(path="diff")),
            dict(title="this", body="", comments=[], diffs=[dict(path="path", diff="diff")]),
        ),
        (
            {"gitlab_api_key": "key"},
            "patchwork.common.client.scm.GitlabClient.get_pr_by_url",
            dict(title="", body="that", comments=[], diffs=dict(path="diff")),
            dict(title="", body="that", comments=[], diffs=[dict(path="path", diff="diff")]),
        ),
        (
            {"github_api_key": "key"},
            "patchwork.common.client.scm.GithubClient.get_pr_by_url",
            dict(title="", body="", comments=[], diffs={f"path{ext}": "diff" for ext in _IGNORED_EXTENSIONS}),
            dict(title="", body="", comments=[], diffs=[]),
        ),
    ],
)
def test_read_prdiffs(mocker, inputs_extra, method_path, texts, expected):
    # Set up
    """Tests the functionality of the ReadPRDiffs class by mocking dependencies and verifying the output.
    
    Args:
        mocker (mocker.MagicMock): A mock object used to replace dependencies in the test.
        inputs_extra (dict): A dictionary containing additional input parameters for the PR.
        method_path (str): The path to the method that interacts with the SCM client to be mocked.
        texts (list): A list of texts that the mocked Pull Request (PR) should return.
        expected (any): The expected output from the run() method of ReadPRDiffs.
    
    Returns:
        None
    """
    base_inputs = {"pr_url": "https://example.com/pr"}
    inputs = {**base_inputs, **inputs_extra}

    mocked_pr = mocker.Mock(spec=PullRequestProtocol)
    mocked_pr.texts.return_value = texts
    mocked_scm_client = mocker.patch(method_path)
    mocked_scm_client.return_value = mocked_pr

    # Actual Run
    read_pr_diffs = ReadPRDiffs(inputs)
    results = read_pr_diffs.run()

    # Assertions
    assert results == expected
