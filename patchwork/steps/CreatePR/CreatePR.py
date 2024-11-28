from pathlib import Path

import git
from git.exc import GitCommandError

from patchwork.common.client.scm import (
    GithubClient,
    GitlabClient,
    ScmPlatformClientProtocol,
    get_slug_from_remote_url,
)
from patchwork.logger import logger
from patchwork.step import Step, StepStatus


class CreatePR(Step):
    required_keys = {"target_branch"}

    def __init__(self, inputs: dict):
        """Initializes the PR creation process with the given inputs.
        
        Args:
            inputs dict: A dictionary containing the input parameters required for initializing the PR creation, including 'scm_url', 'github_api_key', 'gitlab_api_key', 'pr_body', 'pr_title', 'force_pr_creation', 'base_branch', and 'target_branch'.
        
        Raises:
            ValueError: If any of the required keys are missing from the inputs.
        
        Returns:
            None
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.original_remote_name = "origin"

        self.enabled = not bool(inputs.get("disable_pr", False))
        if self.enabled:
            self.scm_client = None
            if "github_api_key" in inputs.keys():
                self.scm_client = GithubClient(inputs["github_api_key"])
            elif "gitlab_api_key" in inputs.keys():
                self.scm_client = GitlabClient(inputs["gitlab_api_key"])
            else:
                logger.warning(
                    f'Missing required input data: "github_api_key" or "gitlab_api_key",'
                    f" PR creation will be disabled."
                )
                self.enabled = False

        if self.enabled:
            if "scm_url" in inputs.keys():
                self.scm_client.set_url(inputs["scm_url"])

            if not self.scm_client.test():
                logger.warning(
                    f"{self.scm_client.__class__.__name__} token test failed. " f"PR creation will be disabled."
                )
                self.enabled = False

        self.pr_body = inputs.get("pr_body", "")
        self.title = inputs.get("pr_title", "Patchwork PR")
        self.force = bool(inputs.get("force_pr_creation", False))
        self.base_branch = inputs.get("base_branch")
        if self.enabled and self.base_branch is None:
            logger.warn("Base branch not provided. Skipping PR creation.")
            self.enabled = False
        self.target_branch = inputs["target_branch"]
        if self.enabled and self.base_branch == self.target_branch:
            logger.warn("Base branch and target branch are the same. Skipping PR creation.")
            self.enabled = False

    def __push(self, repo):
        """Push changes to the specified remote repository branch.
        
        Args:
            repo (Repo): The repository object representing the remote repository to which changes will be pushed.
        
        Returns:
            bool: True if the push was successful, False otherwise.
        """
        push_args = ["--set-upstream", self.original_remote_name, self.target_branch]
        if self.force:
            push_args.insert(0, "--force")

        is_push_success = push(repo, push_args)
        logger.debug(f"Pushed to {self.original_remote_name}/{self.target_branch}")
        return is_push_success

    def run(self) -> dict:
        """Execute the run process, which handles the pushing of changes to a remote repository and creates a pull request if conditions are met.
        
        This method checks the status of the current operation and determines whether to push changes to the target branch or skip pull request creation based on the configuration settings. It logs relevant information regarding the process and returns the URL of the created pull request.
        
        Args:
            self (RunProcess): An instance of the RunProcess class, which contains settings such as enabled status, base and target branches, title, and body for the pull request.
        
        Returns:
            dict: A dictionary containing the pull request URL if creation is successful; otherwise, an empty dictionary.
        """
        repo = git.Repo(Path.cwd(), search_parent_directories=True)
        if not self.enabled:
            if (
                self.base_branch == self.target_branch
                and len(list(repo.iter_commits(f"{self.target_branch}@{{u}}..{self.target_branch}"))) > 0
            ):
                is_push_success = self.__push(repo)
                if not is_push_success:
                    self.set_status(
                        StepStatus.FAILED,
                        f"Failed to push to {self.original_remote_name}/{self.target_branch}. Skipping PR creation.",
                    )
                return dict()

            self.set_status(StepStatus.WARNING, "PR creation is disabled. Skipping PR creation.")
            logger.warning(f"PR creation is disabled. Skipping PR creation.")
            return dict()

        is_push_success = self.__push(repo)
        if not is_push_success:
            self.set_status(
                StepStatus.FAILED,
                f"Failed to push to {self.original_remote_name}/{self.target_branch}. Skipping PR creation.",
            )
            return dict()

        logger.info(f"Creating PR from {self.base_branch} to {self.target_branch}")
        original_remote_url = repo.remotes[self.original_remote_name].url
        repo_slug = get_slug_from_remote_url(original_remote_url)
        url = create_pr(
            repo_slug=repo_slug,
            title=self.title,
            body=self.pr_body,
            base_branch_name=self.base_branch,
            target_branch_name=self.target_branch,
            scm_client=self.scm_client,
            force=self.force,
        )

        logger.info(f"[green]PR created at [link={url}]{url}[/link][/]", extra={"markup": True})
        return {"pr_url": url}


def push(repo: git.Repo, args) -> bool:
    """Attempts to push changes to a specified Git repository.
    
    Args:
        repo (git.Repo): The Git repository to push changes to.
        args: Additional arguments to be passed to the Git push command.
    
    Returns:
        bool: True if the push operation was successful, False otherwise.
    """
    try:
        with repo.git.custom_environment(GIT_TERMINAL_PROMPT="0"):
            repo.git.push(*args)
        return True
    except GitCommandError as e:
        logger.error("Git command failed with:")
        logger.error(e.stdout)
        logger.error(e.stderr)

    freeze_func = getattr(logger, "freeze", None)
    if freeze_func is None:
        return False

    try:
        with logger.freeze():
            repo.git.push(*args)
        return True
    except GitCommandError as e:
        logger.error("Git command failed with:")
        logger.error(e.stdout)
        logger.error(e.stderr)

    return False


def create_pr(
    repo_slug: str,
    body: str,
    title: str,
    base_branch_name: str,
    target_branch_name: str,
    scm_client: ScmPlatformClientProtocol,
    force: bool = False,
):
    """Creates a pull request (PR) for a specified repository.
    
    Args:
        repo_slug (str): The identifier for the repository, typically in the format 'owner/repo'.
        body (str): The description or body of the pull request.
        title (str): The title of the pull request.
        base_branch_name (str): The name of the base branch for the pull request.
        target_branch_name (str): The name of the target branch for the pull request.
        scm_client (ScmPlatformClientProtocol): An instance of a client that interacts with the source control management platform.
        force (bool, optional): If True, updates the PR description even if a PR already exists. Defaults to False.
    
    Returns:
        str: The URL of the created or updated pull request, or an empty string if a PR already exists and 'force' is not set to True.
    """
    prs = scm_client.find_prs(repo_slug, original_branch=base_branch_name, feature_branch=target_branch_name)
    pr = next(iter(prs), None)
    if pr is None:
        pr = scm_client.create_pr(
            repo_slug,
            title,
            body,
            base_branch_name,
            target_branch_name,
        )

        pr.set_pr_description(body)

        return pr.url()

    if force:
        pr.set_pr_description(body)
        return pr.url()

    logger.error(
        f"PR with the same base branch, {base_branch_name}, and target branch, {target_branch_name},"
        f" already exists. Skipping PR creation."
    )
    return ""
