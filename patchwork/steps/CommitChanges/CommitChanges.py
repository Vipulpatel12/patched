from __future__ import annotations

import contextlib
from pathlib import Path

import git
from git import Repo
from typing_extensions import Generator

from patchwork.common.utils.filter_paths import PathFilter
from patchwork.common.utils.utils import get_current_branch
from patchwork.logger import logger
from patchwork.step import Step, StepStatus


@contextlib.contextmanager
def transitioning_branches(
    repo: Repo, branch_prefix: str, branch_suffix: str = "", force: bool = True, enabled: bool = True
) -> Generator[tuple[str, str], None, None]:
    """Creates a new branch in the specified repository based on the current branch.
    
    Args:
        repo Repo: The repository instance in which the branch is to be created.
        branch_prefix str: The prefix to prepend to the new branch name.
        branch_suffix str: An optional suffix to append to the new branch name. Defaults to an empty string.
        force bool: A flag indicating whether to overwrite an existing branch. Defaults to True.
        enabled bool: A flag that enables or disables branch transition. If disabled, returns the current branch without creating a new one. Defaults to True.
    
    Returns:
        Generator[tuple[str, str], None, None]: A generator yielding tuples containing the current branch name and the newly created branch name.
    """
    if not enabled:
        from_branch = get_current_branch(repo)
        from_branch_name = from_branch.name if not from_branch.is_remote() else from_branch.remote_head
        yield from_branch_name, from_branch_name
        return

    from_branch = get_current_branch(repo)
    from_branch_name = from_branch.name if not from_branch.is_remote() else from_branch.remote_head
    next_branch_name = f"{branch_prefix}{from_branch_name}{branch_suffix}"
    if next_branch_name in repo.heads and not force:
        raise ValueError(f'Local Branch "{next_branch_name}" already exists.')
    if next_branch_name in repo.remote("origin").refs and not force:
        raise ValueError(f'Remote Branch "{next_branch_name}" already exists.')

    logger.info(f'Creating new branch "{next_branch_name}".')
    to_branch = repo.create_head(next_branch_name, force=force)

    try:
        to_branch.checkout()
        yield from_branch_name, next_branch_name
    finally:
        from_branch.checkout()


class _EphemeralGitConfig:
    _DEFAULT = -2378137912

    def __init__(self, repo: Repo):
        """Initializes a new instance of the class with the provided repository.
        
        Args:
            repo Repo: An instance of the Repo class to be associated with this instance.
        
        Returns:
            None
        """
        self._repo = repo
        self._keys: set[tuple[str, str]] = set()
        self._original_values: dict[tuple[str, str], str] = dict()
        self._modified_values: dict[tuple[str, str], str] = dict()

    def set_value(self, section: str, option: str, value: str):
        """Sets the value of a specific option within a given section.
        
        Args:
            section str: The name of the section where the option is located.
            option str: The name of the option to be set.
            value str: The value to assign to the specified option.
        
        Returns:
            None: This method does not return a value.
        """
        self._keys.add((section, option))
        self._modified_values[(section, option)] = value

    @contextlib.contextmanager
    def context(self):
        """Yields a context for modifying values while ensuring that any changes are reverted afterward.
        
        This method handles the setup and teardown of value modifications. It persists values that will be modified at the beginning and ensures that any modifications are undone when the context is exited.
        
        Args:
            None
        
        Returns:
            Generator: A generator that allows for the execution of code within the context of modified values.
        """
        try:
            self._persist_values_to_be_modified()
            yield
        finally:
            self._undo_modified_values()

    def _persist_values_to_be_modified(self):
        """Persist values that are to be modified in the repository configuration.
        
        This method reads the current values of specified configuration options
        from the repository. If the original value differs from a predefined 
        default value, it stores those original values for potential later use.
        The method then writes modified values back to the repository, ensuring
        values are updated appropriately and resources are released afterward.
        
        Args:
            self: The instance of the class invoking this method.
        
        Returns:
            None: This method does not return any value.
        """
        reader = self._repo.config_reader("repository")
        for section, option in self._keys:
            original_value = reader.get_value(section, option, self._DEFAULT)
            if original_value != self._DEFAULT:
                self._original_values[(section, option)] = original_value

        writer = self._repo.config_writer()
        try:
            for section, option in self._keys:
                writer.set_value(section, option, self._modified_values[(section, option)])
        finally:
            writer.release()

    def _undo_modified_values(self):
        """Restores modified configuration values to their original state.
        
        This method iterates through a collection of configuration keys and either restores their original values or removes them if they were not present originally. It ensures that all modifications are undone and releases the writer object afterwards.
        
        Args:
            None
        
        Returns:
            None
        """
        writer = self._repo.config_writer()
        try:
            for section, option in self._keys:
                original_value = self._original_values.get((section, option), None)
                if original_value is None:
                    writer.remove_option(section, option)
                else:
                    writer.set_value(section, option, original_value)
        finally:
            writer.release()


def commit_with_msg(repo: Repo, msg: str):
    """Commits changes to a Git repository with a specified commit message using a temporary Git configuration.
    
    Args:
        repo Repo: An instance of a Git repository on which the commit will be performed.
        msg str: The commit message to be associated with the commit.
    
    Returns:
        None: This function does not return a value but commits changes to the repository.
    """
    ephemeral = _EphemeralGitConfig(repo)
    ephemeral.set_value("user", "name", "patched.codes[bot]")
    ephemeral.set_value("user", "email", "298395+patched.codes[bot]@users.noreply.github.com")

    with ephemeral.context():
        repo.git.commit(
            "--author",
            "patched.codes[bot]<298395+patched.codes[bot]@users.noreply.github.com>",
            "-m",
            msg,
        )


class CommitChanges(Step):
    required_keys = {"modified_code_files"}

    def __init__(self, inputs: dict):
        """Initializes an instance of the class with the provided inputs.
        
        Args:
            inputs dict: A dictionary containing required configuration parameters for initialization. It must include 
                          keys specified in self.required_keys, 'modified_code_files', and may include optional keys 
                          such as 'disable_branch', 'force_branch_creation', 'branch_prefix', and 'branch_suffix'.
        
        Raises:
            ValueError: If any required keys are missing from the inputs or if both branch_prefix and branch_suffix 
                        are empty.
        
        Attributes:
            enabled bool: A flag indicating whether the branch is enabled for creation based on the input values.
            modified_code_files list: A list of modified code files to commit changes for.
            force bool: A flag indicating whether to force branch creation.
            branch_prefix str: The prefix to use for the branch name.
            branch_suffix str: The suffix to use for the branch name.
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.enabled = not bool(inputs.get("disable_branch"))

        self.modified_code_files = inputs["modified_code_files"]
        if len(self.modified_code_files) < 1:
            logger.warn("No modified files to commit changes for.")
            self.enabled = False

        self.force = inputs.get("force_branch_creation", True)
        self.branch_prefix = inputs.get("branch_prefix", "patchwork-")
        self.branch_suffix = inputs.get("branch_suffix", "")
        if self.enabled and self.branch_prefix == "" and self.branch_suffix == "":
            raise ValueError("Both branch_prefix and branch_suffix cannot be empty")

    def __get_repo_tracked_modified_files(self, repo: Repo) -> set[Path]:
        """Retrieves a set of modified files tracked by the specified repository, excluding those ignored by the .gitignore file.
        
        Args:
            repo Repo: The repository from which to retrieve the modified files.
        
        Returns:
            set[Path]: A set of Paths representing the modified files tracked by the repository.
        """
        repo_dir_path = Path(repo.working_tree_dir)
        path_filter = PathFilter(repo.working_tree_dir)

        repo_changed_files = set()
        for item in repo.index.diff(None):
            repo_changed_file = Path(item.a_path)
            possible_ignored_grok = path_filter.get_grok_ignored(repo_changed_file)
            if possible_ignored_grok is not None:
                logger.warn(f'Ignoring file: {item.a_path} because of "{possible_ignored_grok}" in .gitignore file.')
                continue
            repo_changed_files.add(repo_dir_path / repo_changed_file)

        return repo_changed_files

    def run(self) -> dict:
        """Runs the process of adding, committing, and pushing modified or untracked files in a Git repository.
        
        This method checks for modified and untracked files in the current Git repository, adds them to staging, commits them with a message, and returns the names of the source and target branches. If no files are found to commit, it skips the operation and returns the current branch name.
        
        Args:
            self (Object): The instance of the class.
        
        Returns:
            dict: A dictionary containing the base branch and the target branch if files were committed; otherwise, it contains the target branch with no changes.
        """
        cwd = Path.cwd()
        repo = git.Repo(cwd, search_parent_directories=True)
        repo_dir_path = Path(repo.working_tree_dir)
        repo_changed_files = self.__get_repo_tracked_modified_files(repo)
        repo_untracked_files = {repo_dir_path / item for item in repo.untracked_files}
        modified_files = {Path(modified_code_file["path"]).resolve() for modified_code_file in self.modified_code_files}
        true_modified_files = modified_files.intersection(repo_changed_files.union(repo_untracked_files))
        if len(true_modified_files) < 1:
            self.set_status(
                StepStatus.SKIPPED, "No file found to add, commit and push. Branch creation will be disabled."
            )
            from_branch = get_current_branch(repo)
            from_branch_name = from_branch.name if not from_branch.is_remote() else from_branch.remote_head
            return dict(target_branch=from_branch_name)

        with transitioning_branches(
            repo,
            branch_prefix=self.branch_prefix,
            branch_suffix=self.branch_suffix,
            force=self.force,
            enabled=self.enabled,
        ) as (
            from_branch,
            to_branch,
        ):
            for modified_file in true_modified_files:
                repo.git.add(modified_file)
                commit_with_msg(repo, f"Patched {modified_file}")

            return dict(
                base_branch=from_branch,
                target_branch=to_branch,
            )
