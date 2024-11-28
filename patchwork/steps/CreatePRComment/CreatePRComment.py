from patchwork.common.client.scm import GithubClient, GitlabClient
from patchwork.logger import logger
from patchwork.step import Step, StepStatus


class CreatePRComment(Step):
    required_keys = {"pr_url", "pr_comment"}

    def __init__(self, inputs: dict):
        """Initializes an SCM client based on the provided input dictionary.
        
        Args:
            inputs dict: A dictionary containing the required input data, which may include 
                          'github_api_key', 'gitlab_api_key', 'scm_url', 'pr_url', 'pr_comment', 
                          and an optional 'noisy_comments' flag.
        
        Raises:
            ValueError: If required keys are missing or if neither 'github_api_key' nor 
                         'gitlab_api_key' is provided.
        
        Attributes:
            scm_client: An instance of GithubClient or GitlabClient based on the provided API key.
            pr: The pull request object retrieved using the provided 'pr_url'.
            pr_comment: The comment associated with the pull request.
            noisy: A boolean indicating if noisy comments are enabled.
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        if "github_api_key" in inputs.keys():
            self.scm_client = GithubClient(inputs["github_api_key"])
        elif "gitlab_api_key" in inputs.keys():
            self.scm_client = GitlabClient(inputs["gitlab_api_key"])
        else:
            raise ValueError(f'Missing required input data: "github_api_key" or "gitlab_api_key"')

        if "scm_url" in inputs.keys():
            self.scm_client.set_url(inputs["scm_url"])

        self.pr = self.scm_client.get_pr_by_url(inputs["pr_url"])
        self.pr_comment = inputs["pr_comment"]
        self.noisy = bool(inputs.get("noisy_comments", False))

    def run(self) -> dict:
        """Executes the process of creating a comment on a pull request and resets comments if not noisy.
        
        Args:
            self: The instance of the class which contains the properties used in the method.
        
        Returns:
            dict: A dictionary containing the URL of the pull request.
        """ 
        if not self.noisy:
            self.pr.reset_comments()

        comment = self.pr.create_comment(body=self.pr_comment)
        if comment is None:
            self.set_status(StepStatus.FAILED)
            logger.error(f"Failed to create comment: {self.pr_comment}")
        else:
            logger.info(f"Comment created for PR: {self.pr.url()}")

        return dict(pr_url=self.pr.url())
