import string
from random import choices

import pytest
from slack_sdk import WebClient

from patchwork.steps.SlackMessage.SlackMessage import SlackMessage


@pytest.fixture
def mocked_slack_key():
    """Generates a mocked Slack key consisting of random letters and digits.
    
    Returns:
        str: A string of 12 random characters chosen from ASCII letters and digits.
    """
    return "".join(choices(string.ascii_letters + string.digits, k=12))


@pytest.fixture
def mocked_slack_client(mocker, mocked_slack_key):
    """Creates a mocked Slack WebClient for testing purposes.
    
    Args:
        mocker: The mocker instance used to create and manage mock objects.
        mocked_slack_key: A pre-defined key for Slack authentication.
    
    Returns:
        MagicMock: A mocked instance of the Slack WebClient with predefined return values for certain methods.
    """
    mocked_slack_client = mocker.MagicMock()
    mocker.patch.object(WebClient, "__new__", return_value=mocked_slack_client)

    mocked_slack_client.auth_test.return_value = {"ok": True}
    mocked_slack_client.auth_teams_list.return_value = {"ok": True, "teams": [{"id": "team-id", "name": "team-name"}]}
    mocked_slack_client.conversations_list.return_value = {
        "ok": True,
        "channels": [{"id": "channel-id", "name": "channel-name"}],
    }
    return mocked_slack_client


def test_slack_message_init_valid_inputs(mocked_slack_client, mocked_slack_key):
    """Tests the initialization of the SlackMessage class with valid inputs.
    
    Args:
        mocked_slack_client (Mock): A mocked instance of the Slack client for testing purposes.
        mocked_slack_key (str): A mocked Slack token to authenticate the Slack client.
    
    Returns:
        None: This function does not return a value.
    """
    inputs = {
        "slack_token": mocked_slack_key,
        "slack_channel": "channel-name",
        "slack_message_template": "Hello {{name}}!",
        "slack_message_template_values": {"name": "John"},
    }
    slack_message = SlackMessage(inputs)
    assert slack_message.slack_channel == "channel-id"
    assert slack_message.slack_message == "Hello John!"


@pytest.mark.parametrize(
    "inputs",
    [
        {
            "slack_channel": "channel-name",
            "slack_message_template": "Hello {{name}}!",
            "slack_message_template_values": {"name": "John"},
        },
        {
            "slack_token": "valid-token",
            "slack_message_template": "Hello {{name}}!",
            "slack_message_template_values": {"name": "John"},
        },
        {
            "slack_token": "valid-token",
            "slack_channel": "channel-name",
            "slack_message_template_values": {"name": "John"},
        },
        {"slack_token": "valid-token", "slack_channel": "channel-name"},
        {
            "slack_token": "valid-token",
            "slack_team": "wrong-name",
            "slack_channel": "channel-name",
            "slack_message_template": "Hello {{name}}!",
        },
        {
            "slack_token": "valid-token",
            "slack_team": "team-name",
            "slack_channel": "wrong-name",
            "slack_message_template": "Hello {{name}}!",
        },
    ],
)
def test_slack_message_init_missing_required_key(mocked_slack_client, mocked_slack_key, inputs):
    """Tests the initialization of the SlackMessage class when a required key is missing.
    
    This test checks that a ValueError is raised when the initialization of 
    the SlackMessage class is attempted with an incomplete set of required 
    parameters, specifically confirming that the absence of the 
    'slack_token' leads to the expected error.
    
    Args:
        mocked_slack_client (Mock): A mock instance of the Slack client used for testing.
        mocked_slack_key (str): A mock representation of a valid Slack key for authentication.
        inputs (dict): A dictionary of input parameters for initializing the SlackMessage.
    
    Returns:
        None: This function does not return any value; it performs an assertion.
    """
    if "slack_token" in inputs:
        inputs["slack_token"] = mocked_slack_key
    with pytest.raises(ValueError):
        SlackMessage(inputs)


def test_slack_message_run(mocked_slack_client, mocked_slack_key):
    """Tests the functionality of sending a Slack message using the SlackMessage class.
    
    Args:
        mocked_slack_client (Mock): A mock instance of the Slack client used to simulate sending a message.
        mocked_slack_key (str): A mocked Slack API token used for authentication.
    
    Returns:
        None: This function does not return a value; it asserts that the message was sent successfully.
    """
    mocked_slack_client.chat_postMessage.return_value = {"ok": True}
    inputs = {
        "slack_token": mocked_slack_key,
        "slack_channel": "channel-name",
        "slack_message_template": "Hello {{name}}!",
        "slack_message_template_values": {"name": "John"},
    }
    slack_message = SlackMessage(inputs)
    result = slack_message.run()
    assert result["is_slack_message_sent"] is True
