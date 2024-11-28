from typing_extensions import List

from patchwork.common.client.scm import GithubClient, GitlabClient
from patchwork.step import Step
from patchwork.steps.ReadPRDiffs.typed import ReadPRDiffsInputs, ReadPRDiffsOutputs

_IGNORED_EXTENSIONS = [
    ".png",
    ".jpg",
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
    """Determine if a given file has one of the specified extensions.
    
    Args:
        file (str): The name of the file to check.
        extensions (list): A list of valid file extensions to match against.
    
    Returns:
        bool: True if the file ends with one of the specified extensions, otherwise False.
    """
    return any(file.endswith(ext) for ext in extensions)


class ReadPRDiffs(Step, input_class=ReadPRDiffsInputs, output_class=ReadPRDiffsOutputs):
    required_keys = {"pr_url"}

    def __init__(self, inputs: dict):
        """Initializes an instance of the class, setting up the source control management client based on provided credentials.
        
        Args:
            inputs dict: A dictionary containing required input parameters including API keys and optional SCM URL.
        
        Raises:
            ValueError: If any of the required keys are missing from the inputs or if neither "github_api_key" nor "gitlab_api_key" is provided.
        
        Returns:
            None
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

    def run(self) -> dict:
        """Runs the process to retrieve and organize pull request texts.
        
        This method collects the title, body, comments, and diffs of a pull request,
        filtering out any diffs with ignored file extensions. It returns a dictionary
        containing the organized information about the pull request.
        
        Args:
            None
        
        Returns:
            dict: A dictionary containing the title, body, comments, and a list of
                  diffs, each represented by a dictionary with 'path' and 'diff' keys.
        """
        pr_texts = self.pr.texts()
        title = pr_texts.get("title", "")
        body = pr_texts.get("body", "")
        comments = pr_texts.get("comments", [])
        diffs: List[dict] = []
        for path, diff_text in pr_texts.get("diffs", {}).items():
            if filter_by_extension(path, _IGNORED_EXTENSIONS):
                continue
            diffs.append(dict(path=path, diff=diff_text))

        return dict(title=title, body=body, comments=comments, diffs=diffs)
