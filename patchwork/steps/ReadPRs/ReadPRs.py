from __future__ import annotations

from patchwork.common.client.scm import (
    GithubClient,
    GitlabClient,
    PullRequestProtocol,
    PullRequestState,
)
from patchwork.logger import logger
from patchwork.step import DataPoint, Step
from patchwork.steps.ReadPRs.typed import ReadPRsInputs

_IGNORED_EXTENSIONS = [
    ".jpeg",
    ".gif",
    ".svg",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".zip",
    ".tar",
    ".gz",
    ".lock",
]


def filter_by_extension(file, extensions):
    """Checks if a given file name ends with any of the specified extensions.
    
    Args:
        file (str): The name of the file to be checked.
        extensions (list): A list of file extensions to compare against.
    
    Returns:
        bool: True if the file ends with any of the specified extensions, False otherwise.
    """
    return any(file.endswith(ext) for ext in extensions)


class ReadPRs(Step):
    def __init__(self, inputs: DataPoint):
        """Initializes the instance of the class with required SCM client setup.
        
        Args:
            inputs DataPoint: A dictionary containing the required input parameters for initializing the SCM client.
        
        Returns:
            None
        """
        super().__init__(inputs)
        missing_keys = ReadPRsInputs.__required_keys__.difference(inputs.keys())
        if len(missing_keys) > 0:
            raise ValueError(f"Missing required data: {missing_keys}")

        if "github_api_key" in inputs.keys():
            self.scm_client = GithubClient(inputs["github_api_key"])
        elif "gitlab_api_key" in inputs.keys():
            self.scm_client = GitlabClient(inputs["gitlab_api_key"])
        else:
            raise ValueError(f'Missing required input data: "github_api_key" or "gitlab_api_key"')

        if "scm_url" in inputs.keys():
            self.scm_client.set_url(inputs["scm_url"])

        self.repo_slug = inputs["repo_slug"]
        self.pr_ids = self.__parse_pr_ids_input(inputs.get("pr_ids"))
        self.pr_state = self.__parse_pr_state_input(inputs.get("pr_state"))
        self.limit = inputs.get("limit", 50)

    @staticmethod
    def __parse_pr_ids_input(pr_ids_input: list[str] | str | None) -> list:
        """Parses a string or a list of pull request IDs into a standardized list format.
        
        Args:
            pr_ids_input (list[str] | str | None): The input containing pull request IDs, which can be a 
                                                    list of strings, a single string, or None.
        
        Returns:
            list: A list of parsed pull request IDs. If the input is None or an empty string, 
                  returns an empty list. If the input is a string, it splits by comma and trims 
                  whitespace; if a list is provided, it returns the list as is.
        """
        if not pr_ids_input:
            return []

        if isinstance(pr_ids_input, str):
            delimiter = None
            if "," in pr_ids_input:
                delimiter = ","
            return [pr_id.strip() for pr_id in pr_ids_input.split(delimiter)]

        if isinstance(pr_ids_input, list):
            return pr_ids_input

        return []

    @staticmethod
    def __parse_pr_state_input(state_input: str | None) -> PullRequestState:
        """Parses the input string to determine the pull request state.
        
        Args:
            state_input (str | None): A string representing the desired pull request state. 
                If the string is None or not valid, defaults to OPEN.
        
        Returns:
            PullRequestState: The corresponding PullRequestState enum value 
                based on the input string, or OPEN if the input is invalid or None.
        """
        if not state_input:
            logger.debug(f"No pull request state given. Defaulting to OPEN.")
            return PullRequestState.OPEN

        state = getattr(PullRequestState, state_input.upper(), None)
        if state is None:
            logger.warning(f"Invalid pull request state: {state_input}. Defaulting to OPEN.")
            return PullRequestState.OPEN

        return state

    def run(self) -> DataPoint:
        """Executes the process of retrieving pull requests and converting them into data points.
        
        This method interacts with the SCM client to find pull requests based on the given repository slug and state. If no pull requests are found, it returns an empty list. If specific pull request IDs are provided, it filters the retrieved pull requests accordingly, converting each to a data point which is then returned as part of a dictionary.
        
        Args:
            self: The instance of the class containing this method.
            
        Returns:
            dict: A dictionary containing a list of data points extracted from the pull requests, under the key 'pr_texts'.
        """
        prs = self.scm_client.find_prs(self.repo_slug, state=self.pr_state, limit=self.limit)
        if len(prs) < 1:
            return dict(pr_texts=[])

        if len(self.pr_ids) > 0:
            prs = filter(lambda _pr: str(_pr.id) in self.pr_ids, prs)

        data_points = []
        for pr in prs:
            data_point = self.__pr_to_data_point(pr)
            data_points.append(data_point)
        return dict(pr_texts=data_points)

    @staticmethod
    def __pr_to_data_point(pr: PullRequestProtocol):
        """Converts a Pull Request object into a standardized data point format.
        
        Args:
            pr PullRequestProtocol: An object representing a pull request, providing methods to access its texts and diffs.
        
        Returns:
            dict: A dictionary containing the title, body, diffs, and comments of the pull request.
        """
        pr_texts = pr.texts()
        title = pr_texts.get("title", "")
        body = pr_texts.get("body", "")
        comments = pr_texts.get("comments", [])
        diffs = []
        for path, diff in pr_texts.get("diffs", {}).items():
            if filter_by_extension(path, _IGNORED_EXTENSIONS):
                continue
            diffs.append(dict(path=path, diff=diff))

        return dict(
            title=title,
            body=body,
            diffs=diffs,
            comments=comments,
        )
