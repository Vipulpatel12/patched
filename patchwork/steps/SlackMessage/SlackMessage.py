from __future__ import annotations

import logging

from patchwork.common.utils.dependency import slack_sdk
from patchwork.step import Step
from patchwork.steps.SlackMessage.typed import SlackMessageInputs


class SlackMessage(Step):
    def __init__(self, inputs):
        """Initializes a Slack message client with the given input parameters.
        
        Args:
            inputs dict: A dictionary containing required inputs for initializing the Slack client, including:
                - slack_token (str): The OAuth token for the Slack API.
                - slack_team (str, optional): The name of the Slack team to filter channels.
                - slack_channel (str): The name of the Slack channel to send messages to.
                - slack_message_template_file (str, optional): The path to a file containing the Slack message template.
                - slack_message_template (str, optional): The raw template string for the Slack message.
                - slack_message_template_values (dict, optional): A dictionary for key-value replacements in the Slack message template.
        
        Raises:
            ValueError: If any required data is missing or invalid, such as an invalid Slack token, non-existent Slack channel, or missing message template.
        
        Returns:
            None
        """
        super().__init__(inputs)
        key_diff = SlackMessageInputs.__required_keys__.difference(inputs.keys())
        if key_diff:
            raise ValueError(f'Missing required data: "{key_diff}"')

        self.slack_client = slack_sdk().WebClient(token=inputs["slack_token"])
        if not self.slack_client.auth_test().get("ok", False):
            raise ValueError("Invalid Slack Token")

        slack_team = inputs.get("slack_team")
        response = self.slack_client.auth_teams_list()
        response_ok = response.get("ok", False)
        if slack_team is not None and not response_ok:
            raise ValueError("Unable to fetch Slack Teams")
        elif not response_ok:
            teams = [None]
        elif slack_team is None:
            teams = [team.get("id") for team in response.get("teams", [])]
        else:
            teams = [team.get("id") for team in response.get("teams", []) if team.get("name") == slack_team]

        slack_channel = inputs["slack_channel"]
        channels: list[str] = []
        for team in teams:
            response = self.slack_client.conversations_list(types="public_channel,private_channel", team=team)
            if not response.get("ok", False):
                raise ValueError("Unable to fetch Slack Channels")
            team_channels: list[str] = [
                channel.get("id") for channel in response.get("channels", []) if channel.get("name") == slack_channel
            ]
            channels.extend(team_channels)

        if len(channels) < 1:
            raise ValueError(f'Slack Channel "{slack_channel}" not found')
        if len(channels) > 1:
            logging.info(f'Multiple Slack Channels found for "{slack_channel}", using the first one.')
        self.slack_channel: str = channels[0]

        slack_template_file = inputs.get("slack_message_template_file")
        if slack_template_file is not None:
            with open(slack_template_file, "r") as fp:
                slack_template = fp.read()
        else:
            slack_template = inputs.get("slack_message_template")
        if slack_template is None:
            raise ValueError('Missing required data: "slack_message_template_file" or "slack_message_template"')

        self.slack_message = slack_template
        slack_template_values = inputs.get("slack_message_template_values")
        if slack_template_values is not None:
            for replacement_key, replacement_value in slack_template_values.items():
                self.slack_message = self.slack_message.replace("{{" + replacement_key + "}}", str(replacement_value))

    def run(self):
        """Sends a message to a specified Slack channel using the Slack client.
        
        Args:
            self.slack_client (SlackClient): An instance of the Slack client used to communicate with the Slack API.
            self.slack_channel (str): The ID or name of the channel where the message will be sent.
            self.slack_message (str): The content of the message to be sent to the channel.
        
        Returns:
            dict: A dictionary containing a key 'is_slack_message_sent' indicating whether the message was successfully sent (True) or not (False).
        """
        response = self.slack_client.chat_postMessage(channel=self.slack_channel, text=self.slack_message)
        return dict(is_slack_message_sent=response.get("ok", False))
