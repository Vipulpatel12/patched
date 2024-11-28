import importlib
from functools import lru_cache

__DEPENDENCY_GROUPS = {
    "rag": ["chromadb"],
    "security": ["semgrep", "depscan"],
    "notification": ["slack_sdk"],
}


@lru_cache(maxsize=None)
def import_with_dependency_group(name):
    """Imports a module by its name and handles import errors by suggesting installation commands.
    
    Args:
        name str: The name of the module to import.
    
    Returns:
        module: The imported module.
    
    Raises:
        ImportError: If the module cannot be imported, an error message is raised suggesting how to install the missing module or its dependency group.
    """ 
    try:
        return importlib.import_module(name)
    except ImportError:
        error_msg = f"Missing dependency for {name}, please `pip install {name}`"
        dependency_group = next(
            (group for group, dependencies in __DEPENDENCY_GROUPS.items() if name in dependencies), None
        )
        if dependency_group is not None:
            error_msg = f"Please `pip install patchwork-cli[{dependency_group}]` to use this step"
        raise ImportError(error_msg)


def chromadb():
    """Imports the 'chromadb' module by utilizing the specified dependency group.
    
    Args:
        None
    
    Returns:
        module: The imported 'chromadb' module.
    """
    return import_with_dependency_group("chromadb")


def slack_sdk():
    """Imports the 'slack_sdk' package with its dependency group.
    
    This function facilitates the import of the 'slack_sdk' library, ensuring that 
    all necessary dependencies are loaded as part of the import process.
    
    Args:
        None
    
    Returns:
        module: The 'slack_sdk' module, ready for use.
    """
    return import_with_dependency_group("slack_sdk")
