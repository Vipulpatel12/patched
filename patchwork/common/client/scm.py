from __future__ import annotations

import functools
import hashlib
import itertools
import time
from enum import Enum
from itertools import chain

import gitlab.const
from attrs import define
from github import Auth, Consts, Github, GithubException, PullRequest
from gitlab import Gitlab, GitlabAuthenticationError, GitlabError
from gitlab.v4.objects import ProjectMergeRequest
from giturlparse import GitUrlParsed, parse
from typing_extensions import Protocol, TypedDict

from patchwork.logger import logger


def get_slug_from_remote_url(remote_url: str) -> str:
    """Extracts a slug from a given remote URL of a repository.
    
    Args:
        remote_url str: The remote URL of the repository from which to extract the slug.
    
    Returns:
        str: The slug constructed from the repository owner, groups, and name.
    """
    parsed_repo: GitUrlParsed = parse(remote_url)
    parts = [parsed_repo.owner, *parsed_repo.groups, parsed_repo.name]
    slug = "/".join(parts)
    return slug


@define
class Comment:
    path: str
    body: str
    start_line: int | None
    end_line: int


class IssueText(TypedDict):
    title: str
    body: str
    comments: list[str]


class PullRequestComment(TypedDict):
    user: str
    body: str


class PullRequestTexts(TypedDict):
    title: str
    body: str
    comments: list[PullRequestComment]
    diffs: dict[str, str]


class PullRequestState(Enum):
    OPEN = (["open"], ["opened"])
    CLOSED = (["closed"], ["closed", "merged"])

    def __init__(self, github_state: list[str], gitlab_state: list[str]):
        """Initializes the configuration for GitHub and GitLab states.
        
        Args:
            github_state list[str]: A list representing the state of GitHub.
            gitlab_state list[str]: A list representing the state of GitLab.
            
        Returns:
            None: This method does not return any value.
        """
        self.github_state: list[str] = github_state
        self.gitlab_state: list[str] = gitlab_state


_COMMENT_MARKER = "<!-- PatchWork comment marker -->"


class PullRequestProtocol(Protocol):
    @property
    def id(self) -> int:
        """Returns the unique identifier for the instance.
        
        Args:
            None
        
        Returns:
            int: The unique identifier of the instance.
        """
        ...

    def url(self) -> str:
        """Returns the URL as a string.
        
        Args:
            None
        
        Returns:
            str: The URL associated with the instance.
        """ 
        ...

    def set_pr_description(self, body: str) -> None:
        """Sets the description for a pull request.
        
        Args:
            body str: The description text to be set for the pull request.
        
        Returns:
            None: This method does not return a value.
        """
        ...

    def create_comment(
        self, body: str, path: str | None = None, start_line: int | None = None, end_line: int | None = None
    ) -> str | None:
        """Creates a comment with the specified body and optional line range.
        
        Args:
            body str: The content of the comment to be created.
            path str | None: The path where the comment should be associated, can be None.
            start_line int | None: The starting line number for the comment, can be None.
            end_line int | None: The ending line number for the comment, can be None.
        
        Returns:
            str | None: The identifier of the created comment, or None if the creation failed.
        """
        ...

    def reset_comments(self) -> None:
        """Resets the comments associated with the instance.
        
        Args:
            None
        
        Returns:
            None: This method does not return any value.
        """ 
        ...

    def texts(self) -> PullRequestTexts:
        """Retrieves the texts associated with the pull request.
        
        Args:
            None
        
        Returns:
            PullRequestTexts: An object containing the texts related to the pull request.
        """
        ...

    @staticmethod
    def _get_template_indexes(template: str) -> tuple[int | None, int | None]:
        """Retrieves the starting and ending indexes of template placeholders within a given string.
        
        Args:
            template str: The string containing template placeholders marked by '{{' and '}}'.
        
        Returns:
            tuple[int | None, int | None]: A tuple containing the starting and ending indexes of the placeholders.
            If no placeholders are found, both values in the tuple will be None.
        """
        start_idx = template.find("{{")
        if start_idx == -1:
            return None, None

        end_idx = template.find("}}", start_idx)
        if end_idx == -1:
            return None, None

        return start_idx, end_idx

    @staticmethod
    def _apply_pr_template(pr: "PullRequestProtocol", body: str) -> str:
        """Applies a template to a pull request or merge request body, replacing placeholders with formatted links based on the request type.
        
        Args:
            pr PullRequestProtocol: An object representing the pull request or merge request. It should be either a GithubPullRequest or a GitlabMergeRequest.
            body str: The body of the template that contains placeholders for link formatting.
        
        Returns:
            str: The formatted template with placeholders replaced by actual links.
        """
        if isinstance(pr, GithubPullRequest):
            backup_link_format = "{url}/files"
            file_link_format = backup_link_format + "#diff-{diff_anchor}"
            chunk_link_format = file_link_format + "L{start_line}-L{end_line}"
            anchor_hash = hashlib.sha256
        elif isinstance(pr, GitlabMergeRequest):
            backup_link_format = "{url}/diffs"
            file_link_format = backup_link_format + "#{diff_anchor}"
            # TODO: deal with gitlab line links
            # chunk_link_format = file_link_format + "_{start_line}_{end_line}"
            chunk_link_format = file_link_format + ""
            anchor_hash = hashlib.sha1
        else:
            return pr.url()

        template = body
        start_idx, end_idx = PullRequestProtocol._get_template_indexes(template)
        while start_idx is not None and end_idx is not None:
            template_content = template[start_idx + 2 : end_idx]

            split_parts = template_content.split(":")
            split_parts_iter = iter(split_parts)
            path = next(split_parts_iter, None)
            start = next(split_parts_iter, None)
            end = next(split_parts_iter, None)

            diff_anchor = ""
            format_to_use = backup_link_format
            if path is not None:
                diff_anchor = anchor_hash(path.encode()).hexdigest()
                format_to_use = file_link_format
                if start is not None and end is not None:
                    format_to_use = chunk_link_format

            replacement_value = format_to_use.format(
                url=pr.url(), diff_anchor=diff_anchor, start_line=start, end_line=end
            )
            template = template[:start_idx] + replacement_value + template[end_idx + 2 :]
            start_idx, end_idx = PullRequestProtocol._get_template_indexes(template)

        return template


class ScmPlatformClientProtocol(Protocol):
    def test(self) -> bool:
        """A test method that performs a specific check.
        
        Args:
            None
        
        Returns:
            bool: Indicates the success or failure of the test.
        """
        ...

    def set_url(self, url: str) -> None:
        """Sets the URL for the instance.
        
        Args:
            url str: The URL to be set for the instance.
        
        Returns:
            None: This method does not return a value.
        """
        ...

    def get_slug_and_id_from_url(self, url: str) -> tuple[str, int] | None:
        """Extracts the slug and ID from a given URL.
        
        Args:
            url str: The URL string from which to extract the slug and ID.
        
        Returns:
            tuple[str, int] | None: A tuple containing the slug as a string and the ID as an integer, or None if extraction fails.
        """
        ...

    def find_issue_by_url(self, url: str) -> IssueText | None:
        """Retrieves an issue based on the provided URL.
        
        Args:
            url str: The URL associated with the issue to be retrieved.
        
        Returns:
            IssueText | None: An IssueText object if an issue is found; otherwise, returns None.
        """
        ...

    def find_issue_by_id(self, slug: str, issue_id: int) -> IssueText | None:
        """Retrieve an issue by its unique identifier.
        
        Args:
            slug str: A string representing the unique slug associated with the issue.
            issue_id int: An integer representing the unique ID of the issue to be retrieved.
        
        Returns:
            IssueText | None: An instance of IssueText if the issue is found, or None if no issue with the given ID exists.
        """
        ...

    def get_pr_by_url(self, url: str) -> PullRequestProtocol | None:
        """Retrieves a pull request based on the provided URL.
        
        Args:
            url str: The URL of the pull request to be retrieved.
        
        Returns:
            PullRequestProtocol | None: The pull request object if found, otherwise None.
        """ 
        ...

    def find_pr_by_id(self, slug: str, pr_id: int) -> PullRequestProtocol | None:
        """Retrieves a pull request by its unique identifier.
        
        Args:
            slug str: The unique identifier for the repository.
            pr_id int: The unique identifier for the pull request.
        
        Returns:
            PullRequestProtocol | None: An instance of PullRequestProtocol if the pull request is found, otherwise None.
        """
        ...

    def find_prs(
        self,
        slug: str,
        state: PullRequestState | None = None,
        original_branch: str | None = None,
        feature_branch: str | None = None,
        limit: int | None = None,
    ) -> list[PullRequestProtocol]:
        """Finds pull requests based on the specified criteria.
        
        Args:
            slug str: The unique identifier for the repository in the format 'owner/repo'.
            state PullRequestState | None: The state of the pull requests to filter by (e.g., open, closed).
            original_branch str | None: The name of the original branch to filter the pull requests.
            feature_branch str | None: The name of the feature branch to filter the pull requests.
            limit int | None: The maximum number of pull requests to return.
        
        Returns:
            list[PullRequestProtocol]: A list of pull request objects matching the specified criteria.
        """
        ...

    def create_pr(
        self,
        slug: str,
        title: str,
        body: str,
        original_branch: str,
        feature_branch: str,
    ) -> PullRequestProtocol:
        """Creates a pull request with the given details.
        
        Args:
            slug str: The unique identifier for the repository in the format 'owner/repo'.
            title str: The title of the pull request.
            body str: The detailed description of the pull request.
            original_branch str: The branch from which the pull request is being created.
            feature_branch str: The branch to which the pull request will be merged.
        
        Returns:
            PullRequestProtocol: An object representing the created pull request.
        """
        ...

    def create_issue_comment(
        self, slug: str, issue_text: str, title: str | None = None, issue_id: int | None = None
    ) -> str:
        """Creates a comment on a specified issue.
        
        Args:
            slug str: The unique identifier for the issue or project where the comment is to be made.
            issue_text str: The content of the comment to be added to the issue.
            title str | None: An optional title for the comment. If not provided, a default title may be used.
            issue_id int | None: An optional identifier for the specific issue. If not provided, the comment will be added to the issue identified by the slug.
        
        Returns:
            str: A confirmation message or the identifier of the created comment.
        """
        ...


class GitlabMergeRequest(PullRequestProtocol):
    def __init__(self, mr: ProjectMergeRequest):
        """Initializes an instance of the class with a given merge request.
        
        Args:
            mr ProjectMergeRequest: An object representing a merge request.
        
        Returns:
            None
        """
        self._mr = mr

    @property
    def id(self) -> int:
        """Retrieves the unique identifier of the current instance.
        
        Args:
            None
        
        Returns:
            int: The unique identifier associated with the instance.
        """
        return self._mr.iid

    def url(self) -> str:
        """Returns the web URL associated with the instance.
        
        Args:
            None
        
        Returns:
            str: The web URL as a string.
        """
        return self._mr.web_url

    def set_pr_description(self, body: str) -> None:
        """Sets the description of the merge request using a specified template.
        
        Args:
            body str: The raw body of the description to be formatted and applied.
        
        Returns:
            None: This method does not return a value.
        """
        self._mr.description = PullRequestProtocol._apply_pr_template(self, body)
        self._mr.save()

    def create_comment(
        self, body: str, path: str | None = None, start_line: int | None = None, end_line: int | None = None
    ) -> str | None:
        """Creates a comment or discussion on a merge request.
        
        Args:
            body (str): The content of the comment to be added.
            path (str | None): The file path associated with the comment, if any.
            start_line (int | None): The starting line number for the comment, if applicable.
            end_line (int | None): The ending line number for the comment, if applicable.
        
        Returns:
            str | None: Returns the identifier of the created note in the format '#note_<id>' if successful, otherwise returns None.
        """
        final_body = f"{_COMMENT_MARKER} \n{PullRequestProtocol._apply_pr_template(self, body)}"
        if path is None:
            note = self._mr.notes.create({"body": final_body})
            return f"#note_{note.get_id()}"

        commit = None
        for i in range(3):
            try:
                commit = self._mr.commits().next()
            except StopIteration:
                time.sleep(2**i)

        if commit is None:
            return None

        diff = None
        for i in range(3):
            try:
                iterator = self._mr.diffs.list(iterator=True)
                diff = iterator.next()  # type: ignore
                if diff.head_commit_sha == commit.get_id():
                    break
            except StopIteration:
                time.sleep(2**i)
                continue

        if diff is None:
            return None

        base_commit = diff.base_commit_sha
        head_commit = diff.head_commit_sha

        try:
            discussion = self._mr.discussions.create(
                {
                    "body": final_body,
                    "position": {
                        "base_sha": base_commit,
                        "start_sha": base_commit,
                        "head_sha": head_commit,
                        "position_type": "text",
                        "old_path": path,
                        "new_path": path,
                        "old_line": end_line,
                        "new_line": end_line,
                    },
                }
            )
        except Exception as e:
            logger.error(e)
            return None

        for note in discussion.attributes["notes"]:
            return f"#note_{note['id']}"

        return None

    def reset_comments(self) -> None:
        """Resets comments in discussions by deleting notes that start with a specific comment marker.
        
        Args:
            self: The instance of the class that contains the method.
        
        Returns:
            None: This method does not return any value.
        """
        for discussion in self._mr.discussions.list(iterator=True):
            for note in discussion.attributes["notes"]:
                if note["body"].startswith(_COMMENT_MARKER):
                    discussion.notes.delete(note["id"])

    def texts(self) -> PullRequestTexts:
        """Retrieves the title, body, comments, and diffs of a merge request.
        
        Args:
            self: The instance of the class containing the merge request.
        
        Returns:
            PullRequestTexts: A dictionary containing the title, body, comments, 
            and a mapping of file paths to their diffs for the latest merge request diff.
        """
        title = self._mr.title
        body = self._mr.description
        notes = [
            dict(user=note.author.get("username") or "", body=note.body)
            for note in self._mr.notes.list(iterator=True)
            if note.system is False and note.author is not None and note.body is not None
        ]

        diffs = self._mr.diffs.list()
        latest_diff = max(diffs, key=lambda diff: diff.created_at, default=None)
        if latest_diff is None:
            return dict(title=title, body=body, comments=notes, diffs={})

        files = self._mr.diffs.get(latest_diff.id).diffs
        return dict(
            title=title,
            body=body,
            comments=notes,
            diffs={file["new_path"]: file["diff"] for file in files if not file["diff"].startswith("Binary files")},
        )


class GithubPullRequest(PullRequestProtocol):
    def __init__(self, pr: PullRequest):
        """Initialize a new instance of the class with a PullRequest object.
        
        Args:
            pr PullRequest: An instance of the PullRequest class that represents the pull request associated with this instance.
        
        Returns:
            None: This constructor does not return a value.
        """
        self._pr: PullRequest = pr

    @property
    def id(self) -> int:
        """Returns the identifier of the current object.
        
        Args:
            None
        
        Returns:
            int: The identifier number associated with the current object.
        """
        return self._pr.number

    def url(self) -> str:
        """Returns the URL of the associated HTML resource.
        
        Args:
            None
        
        Returns:
            str: The HTML URL of the resource.
        """
        return self._pr.html_url

    def set_pr_description(self, body: str) -> None:
        """Sets the description of a pull request by applying a template to the provided body string.
        
        Args:
            body str: The initial description for the pull request that will be modified by the template.
        
        Returns:
            None: This method does not return a value.
        """
        final_body = PullRequestProtocol._apply_pr_template(self, body)
        self._pr.edit(body=final_body)

    def create_comment(
        self, body: str, path: str | None = None, start_line: int | None = None, end_line: int | None = None
    ) -> str | None:
        """Creates a comment on a pull request, either as an issue comment or a review comment.
        
        Args:
            body (str): The text content of the comment to be created.
            path (str | None): The file path to which the comment is associated. If None, creates an issue comment.
            start_line (int | None): The starting line number for the review comment. Required for review comments.
            end_line (int | None): The ending line number for the review comment. Required for review comments.
        
        Returns:
            str | None: The HTML URL of the created comment, or None if the comment could not be created.
        """
        final_body = f"{_COMMENT_MARKER} \n{PullRequestProtocol._apply_pr_template(self, body)}"

        if path is None:
            return self._pr.create_issue_comment(body=final_body).html_url

        kwargs = dict(body=final_body, path=path)
        if start_line is not None:
            kwargs["start_line"] = start_line
            kwargs["start_side"] = "LEFT"
        if end_line is not None:
            kwargs["line"] = end_line
            kwargs["side"] = "LEFT"

        return self._pr.create_review_comment(commit=self._pr.get_commits()[0], **kwargs).html_url  # type: ignore

    def reset_comments(self) -> None:
        """Resets comments associated with a pull request by deleting those that start with a designated marker.
        
        This method retrieves both review comments and issue comments related to the pull request,
        and deletes any comment whose body starts with the specified _COMMENT_MARKER.
        
        Args:
            self: The instance of the class in which this method is defined.
        
        Returns:
            None: This method does not return any value.
        """
        for comment in chain(self._pr.get_review_comments(), self._pr.get_issue_comments()):
            if comment.body.startswith(_COMMENT_MARKER):
                comment.delete()

    def texts(self) -> PullRequestTexts:
        """Retrieves the textual components of a pull request, including its title, body, comments, and diffs.
        
        Args:
            self: The instance of the class containing the pull request data.
        
        Returns:
            PullRequestTexts: A dictionary containing the title, body, comments, and diffs of the pull request.
        """
        return dict(
            title=self._pr.title or "",
            body=self._pr.body or "",
            comments=[
                dict(user=comment.user.name, body=comment.body)
                for comment in itertools.chain(self._pr.get_comments(), self._pr.get_issue_comments())
            ],
            # None checks for binary files
            diffs={file.filename: file.patch for file in self._pr.get_files() if file.patch is not None},
        )


class GithubClient(ScmPlatformClientProtocol):
    DEFAULT_URL = Consts.DEFAULT_BASE_URL

    def __init__(self, access_token: str, url: str = DEFAULT_URL):
        """Initializes an instance of the class with the specified access token and URL.
        
        Args:
            access_token str: The access token required for authentication.
            url str: (Optional) The URL to connect to. Defaults to DEFAULT_URL if not provided.
        
        Returns:
            None: This method does not return a value.
        """ 
        self._access_token = access_token
        self._url = url

    @functools.cached_property
    def github(self) -> Github:
        """Creates and returns a Github client instance authenticated with a personal access token.
        
        Args:
            self: The instance of the class containing the method.
            
        Returns:
            Github: An authenticated Github client instance for interacting with the GitHub API.
        """
        auth = Auth.Token(self._access_token)
        return Github(base_url=self._url, auth=auth)

    def test(self) -> bool:
        """Test method that always returns True.
        
        Returns:
            bool: Always returns True.
        """ 
        return True

    def set_url(self, url: str) -> None:
        """Sets the URL for the instance.
        
        Args:
            url str: The URL to be set for the instance.
        
        Returns:
            None: This method does not return any value.
        """
        self._url = url

    def get_slug_and_id_from_url(self, url: str) -> tuple[str, int] | None:
        """Extracts the slug and resource ID from a given URL.
        
        Args:
            url str: The URL string from which the slug and resource ID will be extracted.
        
        Returns:
            tuple[str, int] | None: A tuple containing the extracted slug and resource ID if successful; 
                                    otherwise, None if the URL is invalid or cannot be parsed.
        """
        url_parts = url.split("/")
        if len(url_parts) < 5:
            logger.error(f"Invalid issue URL: {url}")
            return None

        try:
            resource_id = int(url_parts[-1])
        except ValueError:
            logger.error(f"Invalid issue URL: {url}")
            return None

        slug = "/".join(url_parts[-4:-2])

        return slug, resource_id

    def find_issue_by_url(self, url: str) -> IssueText | None:
        """Finds an issue based on the provided URL.
        
        Args:
            url str: The URL of the issue from which the slug and issue ID will be extracted.
        
        Returns:
            IssueText | None: An IssueText object representing the found issue, or None if not found.
        """
        slug, issue_id = self.get_slug_and_id_from_url(url)
        return self.find_issue_by_id(slug, issue_id)

    def find_issue_by_id(self, slug: str, issue_id: int) -> IssueText | None:
        """Retrieves an issue by its ID from a specified GitHub repository.
        
        Args:
            slug (str): The repository identifier in the format 'owner/repo'.
            issue_id (int): The numerical ID of the issue to retrieve.
        
        Returns:
            IssueText | None: A dictionary containing the issue's title, body, and comments 
                              if the issue is found; otherwise, returns None.
        """
        repo = self.github.get_repo(slug)
        try:
            issue = repo.get_issue(issue_id)
            return dict(
                title=issue.title,
                body=issue.body,
                comments=[issue_comment.body for issue_comment in issue.get_comments()],
            )
        except GithubException as e:
            logger.warn(f"Failed to get issue: {e}")
            return None

    def get_pr_by_url(self, url: str) -> PullRequestProtocol | None:
        """Retrieves a pull request by its URL.
        
        Args:
            url str: The URL of the pull request.
        
        Returns:
            PullRequestProtocol | None: The pull request associated with the URL if found, otherwise None.
        """
        slug, pr_id = self.get_slug_and_id_from_url(url)
        return self.find_pr_by_id(slug, pr_id)

    def find_pr_by_id(self, slug: str, pr_id: int) -> PullRequestProtocol | None:
        """Retrieves a pull request from a GitHub repository by its ID.
        
        Args:
            slug str: The unique identifier of the repository in the format "owner/repo".
            pr_id int: The ID of the pull request to be retrieved.
        
        Returns:
            PullRequestProtocol | None: An instance of the GithubPullRequest if found, otherwise None.
        """
        repo = self.github.get_repo(slug)
        try:
            pr = repo.get_pull(pr_id)
            return GithubPullRequest(pr)
        except GithubException as e:
            logger.warn(f"Failed to get PR: {e}")
            return None

    def find_prs(
        self,
        slug: str,
        state: PullRequestState | None = None,
        original_branch: str | None = None,
        feature_branch: str | None = None,
        limit: int | None = None,
    ) -> list[GithubPullRequest]:
        """Finds pull requests for a given repository based on specified criteria.
        
        Args:
            slug str: The repository identifier in the format 'owner/repo'.
            state PullRequestState | None: The state of the pull requests to filter (e.g., open, closed).
            original_branch str | None: The base branch to filter the pull requests.
            feature_branch str | None: The head branch to filter the pull requests.
            limit int | None: The maximum number of pull requests to return.
        
        Returns:
            list[GithubPullRequest]: A list of pull request objects that match the specified criteria.
        """
        repo = self.github.get_repo(slug)
        kwargs_list = dict(state=[None], target_branch=[None], source_branch=[None])

        if state is not None:
            kwargs_list["state"] = state.github_state  # type: ignore
        if original_branch is not None:
            kwargs_list["base"] = [original_branch]  # type: ignore
        if feature_branch is not None:
            kwargs_list["head"] = [feature_branch]  # type: ignore

        page_list = []
        keys = kwargs_list.keys()
        for instance in itertools.product(*kwargs_list.values()):
            kwargs = dict(((key, value) for key, value in zip(keys, instance) if value is not None))
            pages = repo.get_pulls(**kwargs)
            page_list.append(pages)

        branch_checker = lambda pr: True
        if original_branch is not None:
            branch_checker = lambda pr: branch_checker and pr.base.ref == original_branch
        if feature_branch is not None:
            branch_checker = lambda pr: branch_checker and pr.head.ref == feature_branch

        # filter out PRs that are not the ones we are looking for
        rv_list = []
        for pr in itertools.islice(itertools.chain(*page_list), limit):
            if branch_checker(pr):
                rv_list.append(GithubPullRequest(pr))
        return rv_list

    def create_pr(
        self,
        slug: str,
        title: str,
        body: str,
        original_branch: str,
        feature_branch: str,
    ) -> PullRequestProtocol:
        # before creating a PR, check if one already exists
        """Creates a pull request in the specified GitHub repository.
        
        Args:
            slug str: The repository identifier in the format 'owner/repo'.
            title str: The title of the pull request.
            body str: The body or description of the pull request.
            original_branch str: The branch into which the pull request is to be merged.
            feature_branch str: The branch that contains the changes to be merged.
        
        Returns:
            PullRequestProtocol: An object representing the created pull request.
        """
        repo = self.github.get_repo(slug)
        gh_pr = repo.create_pull(title=title, body=body, base=original_branch, head=feature_branch)
        pr = GithubPullRequest(gh_pr)
        return pr

    def create_issue_comment(
        self, slug: str, issue_text: str, title: str | None = None, issue_id: int | None = None
    ) -> str:
        """Creates a comment on an existing issue or a new issue in a GitHub repository.
        
        Args:
            slug str: The full name of the repository (e.g., 'owner/repo').
            issue_text str: The text content of the comment or issue.
            title str | None: The title of the new issue, if creating a new issue (default is None).
            issue_id int | None: The ID of the existing issue to comment on (default is None).
        
        Returns:
            str: The HTML URL of the created comment or issue.
        """
        repo = self.github.get_repo(slug)
        if issue_id is not None:
            return repo.get_issue(issue_id).create_comment(issue_text).html_url
        else:
            return repo.create_issue(title, issue_text).html_url


class GitlabClient(ScmPlatformClientProtocol):
    DEFAULT_URL = gitlab.const.DEFAULT_URL

    def __init__(self, access_token: str, url: str = DEFAULT_URL):
        """Initializes an instance of the class with the provided access token and optional URL.
        
        Args:
            access_token str: A token used for authentication to access protected resources.
            url str: The base URL for the API (default is DEFAULT_URL).
        
        Returns:
            None: This method does not return a value.
        """ 
        self._access_token = access_token
        self._url = url

    @functools.cached_property
    def gitlab(self) -> Gitlab:
        """Creates a Gitlab client instance using the specified URL and access token.
        
        Args:
            self: The instance of the class containing the method.
            
        Returns:
            Gitlab: An instance of the Gitlab client configured with the provided URL and access token.
        """
        return Gitlab(self._url, private_token=self._access_token)

    def set_url(self, url: str) -> None:
        """Sets the URL for the instance.
        
        Args:
            url str: The URL to be set for the instance.
        
        Returns:
            None: This method does not return a value.
        """ 
        self._url = url

    def test(self) -> bool:
        """Tests the authentication of the GitLab user.
        
        This method attempts to authenticate the user using the GitLab API. 
        If authentication fails due to a GitlabAuthenticationError, it returns False.
        Otherwise, it checks if the GitLab user is not None, indicating successful authentication.
        
        Args:
            None
        
        Returns:
            bool: True if the user is authenticated successfully, False otherwise.
        """
        try:
            self.gitlab.auth()
        except GitlabAuthenticationError:
            return False
        return self.gitlab.user is not None

    def get_slug_and_id_from_url(self, url: str) -> tuple[str, int] | None:
        """Extracts the slug and resource ID from a given URL.
        
        Args:
            url str: The URL from which the slug and resource ID will be extracted.
        
        Returns:
            tuple[str, int] | None: A tuple containing the slug and resource ID if successful, or None if the URL is invalid.
        """
        url_parts = url.split("/")
        if len(url_parts) < 5:
            logger.error(f"Invalid issue URL: {url}")
            return None

        try:
            resource_id = int(url_parts[-1])
        except ValueError:
            logger.error(f"Invalid issue URL: {url}")
            return None

        slug = "/".join(url_parts[-5:-3])

        return slug, resource_id

    def find_issue_by_url(self, url: str) -> IssueText | None:
        """Retrieves an issue based on the provided URL.
        
        Args:
            url str: The URL from which to extract the slug and issue ID.
        
        Returns:
            IssueText | None: An IssueText object if an issue is found, otherwise None.
        """
        slug, issue_id = self.get_slug_and_id_from_url(url)
        return self.find_issue_by_id(slug, issue_id)

    def find_issue_by_id(self, slug: str, issue_id: int) -> IssueText | None:
        """Fetches an issue by its ID from a specified GitLab project.
        
        Args:
            slug (str): The unique identifier for the GitLab project.
            issue_id (int): The ID of the issue to retrieve.
        
        Returns:
            IssueText | None: A dictionary containing the issue's title, body, and comments 
                              if found; otherwise, returns None.
        """
        project = self.gitlab.projects.get(slug)
        try:
            issue = project.issues.get(issue_id)
            return dict(
                title=issue.get("title", ""),
                body=issue.get("description", ""),
                comments=[note["body"] for note in issue.notes.list()],
            )
        except GitlabError as e:
            logger.warn(f"Failed to get issue: {e}")
            return None

    def get_pr_by_url(self, url: str) -> PullRequestProtocol | None:
        """Retrieves a pull request based on the provided URL.
        
        Args:
            url str: The URL of the pull request.
        
        Returns:
            PullRequestProtocol | None: The pull request object if found, otherwise None.
        """ 
        slug, pr_id = self.get_slug_and_id_from_url(url)
        return self.find_pr_by_id(slug, pr_id)

    def find_pr_by_id(self, slug: str, pr_id: int) -> PullRequestProtocol | None:
        """Retrieves a merge request (MR) by its ID from a specified project.
        
        Args:
            slug str: The unique identifier for the project in GitLab.
            pr_id int: The ID of the merge request to retrieve.
        
        Returns:
            PullRequestProtocol | None: The merge request object if found, otherwise None.
        """
        project = self.gitlab.projects.get(slug)
        try:
            mr = project.mergerequests.get(pr_id)
            return GitlabMergeRequest(mr)
        except GitlabError as e:
            logger.warn(f"Failed to get MR: {e}")
            return None

    def find_prs(
        self,
        slug: str,
        state: PullRequestState | None = None,
        original_branch: str | None = None,
        feature_branch: str | None = None,
        limit: int | None = None,
    ) -> list[PullRequestProtocol]:
        """Retrieve a list of merge requests (PRs) for a specified project in GitLab.
        
        Args:
            slug str: The unique identifier for the project (project slug).
            state PullRequestState | None: The state of the pull requests to retrieve (e.g., opened, closed). Default is None.
            original_branch str | None: The target branch of the pull requests. Default is None.
            feature_branch str | None: The source branch of the pull requests. Default is None.
            limit int | None: The maximum number of pull requests to return. Default is None (return all).
        
        Returns:
            list[PullRequestProtocol]: A list of PullRequestProtocol instances representing the retrieved merge requests.
        """
        project = self.gitlab.projects.get(slug)
        kwargs_list = dict(iterator=[True], state=[None], target_branch=[None], source_branch=[None])

        if state is not None:
            kwargs_list["state"] = state.gitlab_state  # type: ignore
        if original_branch is not None:
            kwargs_list["target_branch"] = [original_branch]  # type: ignore
        if feature_branch is not None:
            kwargs_list["source_branch"] = [feature_branch]  # type: ignore

        page_list = []
        keys = kwargs_list.keys()
        for instance in itertools.product(*kwargs_list.values()):
            kwargs = dict(((key, value) for key, value in zip(keys, instance) if value is not None))
            mrs_instance = project.mergerequests.list(**kwargs)
            page_list.append(list(mrs_instance))

        rv_list = []
        for mr in itertools.islice(itertools.chain(*page_list), limit):
            rv_list.append(GitlabMergeRequest(mr))

        return rv_list

    def create_pr(
        self,
        slug: str,
        title: str,
        body: str,
        original_branch: str,
        feature_branch: str,
    ) -> PullRequestProtocol:
        # before creating a PR, check if one already exists
        """Creates a new pull request in the specified GitLab project.
        
        Args:
            slug (str): The identifier of the project in GitLab.
            title (str): The title of the pull request.
            body (str): The description body of the pull request.
            original_branch (str): The branch into which the pull request is to be merged.
            feature_branch (str): The branch from which the pull request is created.
        
        Returns:
            PullRequestProtocol: An object representing the created pull request.
        """
        project = self.gitlab.projects.get(slug)
        gl_mr = project.mergerequests.create(
            {
                "source_branch": feature_branch,
                "target_branch": original_branch,
                "title": title,
                "description": body,
                "labels": "patchwork",
            }
        )
        mr = GitlabMergeRequest(gl_mr)  # type: ignore
        return mr

    def create_issue_comment(
        self, slug: str, issue_text: str, title: str | None = None, issue_id: int | None = None
    ) -> str:
        """Creates a comment on an existing issue or a new issue in a GitLab project.
        
        Args:
            slug str: The project identifier used to fetch the project from GitLab.
            issue_text str: The text content of the comment or description for the new issue.
            title str | None: The title of the new issue (optional, required if creating a new issue).
            issue_id int | None: The ID of the existing issue to comment on (optional).
        
        Returns:
            str: The web URL of the created comment or issue.
        """
        if issue_id is not None:
            obj = self.gitlab.projects.get(slug).issues.get(issue_id).notes.create({"body": issue_text})
            return obj["web_url"]

        obj = self.gitlab.projects.get(slug).issues.create({"title": title, "description": issue_text})
        return obj["web_url"]
