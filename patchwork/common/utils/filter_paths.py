from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import git

IGNORE_DIRS = {
    ".git",
    ".idea",
    "__pycache__",
    ".mvn",
    "node_modules",
}

IGNORE_EXTS_GLOBS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.whl",
    "*.egg",
    "*.egg-info",
    "*.dist-info",
}

IGNORE_FILES_GLOBS = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "mvnw",
    "mvnw.cmd",
    "gradlew",
    "gradlew.bat",
}


class PathFilter:
    def __init__(self, base_path: str | Path = Path.cwd(), ignored_groks: set[str] | None = None, max_depth: int = -1):
        """Initializes an instance of the class.
        
        Args:
            base_path (str | Path): The starting path for the repository, defaults to the current working directory.
            ignored_groks (set[str] | None): A set of ignored patterns; if None, an empty set is used.
            max_depth (int): Maximum depth for traversing directories; -1 means unlimited depth.
        
        Returns:
            None
        """
        self.base_path = Path(base_path)
        self.max_depth = max_depth
        self.__ignored_groks = ignored_groks if ignored_groks is not None else set()
        try:
            self.__repo = git.Repo(base_path, search_parent_directories=True)
            self.__ignored_groks.update(self.__get_gitignore_ignored_groks())
        except git.InvalidGitRepositoryError:
            self.__repo = None

    def __get_gitignore_ignored_groks(self) -> set[str]:
        """Retrieve a set of file patterns that are ignored by the .gitignore file in the current repository.
        
        Args:
            None
        
        Returns:
            set[str]: A set of strings representing the file patterns ignored by the .gitignore file.
        """ 
        ignored_groks = set()
        gitignore_file = Path(self.__repo.working_tree_dir) / ".gitignore"
        if not gitignore_file.is_file():
            return ignored_groks
        lines = gitignore_file.read_text().splitlines()
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("#") or stripped_line == "":
                continue
            ignored_groks.add(stripped_line)
        return ignored_groks

    def get_grok_ignored(self, file_to_test: str | Path) -> str | None:
        """Retrieves the first ignored grok pattern that matches the given file or its parent directories.
        
        Args:
            file_to_test (str | Path): The file or directory path to test against the ignored grok patterns.
        
        Returns:
            str | None: The first matching ignored grok pattern as a string, or None if no match is found.
        """
        file = Path(file_to_test)
        paths_to_test = [file] + list(file.parents)
        for ignored_grok in self.__ignored_groks:
            for path in paths_to_test:
                if fnmatch(str(path), ignored_grok):
                    return ignored_grok
        return None

    def get_depth_ignored(self, file_to_test: str | Path) -> int | None:
        """Calculate the depth of a given file relative to a base path, and determine if it exceeds a specified maximum depth.
        
        Args:
            file_to_test (str | Path): The file path to analyze, which can be provided as a string or a Path object.
        
        Returns:
            int | None: The depth of the file if it exceeds the maximum depth; otherwise, returns None if the max depth is -1 or the file is not within the base path.
        """
        file = Path(file_to_test)
        if self.max_depth == -1:
            return None

        try:
            file_depth = len(file.relative_to(self.base_path).parts)
        except ValueError:
            return None

        if file_depth > self.max_depth:
            return file_depth

        return None
