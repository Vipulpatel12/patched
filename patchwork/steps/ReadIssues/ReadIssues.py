from patchwork.common.client.scm import (
    GithubClient,
    GitlabClient,
    ScmPlatformClientProtocol,
)
from patchwork.step import Step


class ReadIssues(Step):
    required_keys = {"issue_url"}

    def __init__(self, inputs: dict):
        """Initializes an instance of the class, validates input, and sets up the SCM client.
        
        Args:
            inputs dict: A dictionary containing configuration inputs for initialization. 
                         It must include either "github_api_key" or "gitlab_api_key", 
                         and optionally "scm_url" and "issue_url".
        
        Raises:
            ValueError: If required keys are missing from the inputs or if the issue 
                        cannot be found using the provided issue URL.
        
        Returns:
            None: This method does not return a value.
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.scm_client: ScmPlatformClientProtocol
        if "github_api_key" in inputs.keys():
            self.scm_client = GithubClient(inputs["github_api_key"])
        elif "gitlab_api_key" in inputs.keys():
            self.scm_client = GitlabClient(inputs["gitlab_api_key"])
        else:
            raise ValueError(f'Missing required input data: "github_api_key" or "gitlab_api_key"')

        if "scm_url" in inputs.keys():
            self.scm_client.set_url(inputs["scm_url"])

        self.issue = self.scm_client.find_issue_by_url(inputs["issue_url"])
        if not self.issue:
            raise ValueError(f"Could not find issue with url: {inputs['issue_url']}")

    def run(self) -> dict:
        """Retrieves issue details including title, body, and comments.
        
        Args:
            None
        
        Returns:
            dict: A dictionary containing the issue's title, body, and comments.
        """ 
        return dict(
            issue_title=self.issue.get("title"),
            issue_body=self.issue.get("body"),
            issue_comments=self.issue.get("comments"),
        )
