import pytest
from click.testing import CliRunner

from patchwork.app import cli, find_patchflow


@pytest.fixture
def config_dir(tmp_path):
    """Creates a configuration directory within a specified temporary path.
    
    Args:
        tmp_path Path: The temporary path in which to create the configuration directory.
    
    Returns:
        Path: The path to the newly created configuration directory.
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def patchflow_dir(config_dir):
    """Creates a "noop" directory within the specified configuration directory.
    
    Args:
        config_dir Path: The directory in which to create the "noop" directory.
    
    Returns:
        Path: The path of the created "noop" directory.
    """ 
    patchflow_dir = config_dir / "noop"
    patchflow_dir.mkdir(parents=True, exist_ok=True)
    return patchflow_dir


@pytest.fixture
def patchflow_file(patchflow_dir):
    """Creates a file named 'noop.py' in the specified patchflow directory.
    
    Args:
        patchflow_dir (Path): The directory where the 'noop.py' file will be created.
    
    Returns:
        Path: The path to the created 'noop.py' file.
    """
    patchflow_file = patchflow_dir / "noop.py"
    patchflow_file.touch(exist_ok=True)
    return patchflow_file


@pytest.fixture
def config_file(patchflow_dir):
    """Creates a configuration file at the specified directory if it does not exist.
    
    Args:
        patchflow_dir Path: The directory where the configuration file should be created.
    
    Returns:
        Path: The path to the configuration file.
    """ 
    config_file = patchflow_dir / "config.yaml"
    config_file.touch(exist_ok=True)
    return config_file


@pytest.fixture
def runner():
    """Creates an isolated filesystem context for running CLI commands.
    
    This function provides a temporary isolated filesystem environment for
    command-line interface testing using the CliRunner. It yields an instance
    of the runner that can be used within the context.
    
    Returns:
        CliRunner: An instance of CliRunner that can be used to invoke CLI commands
        within an isolated filesystem.
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner
    return


def test_default_list_option_callback(runner):
    """Tests the default behavior of the list option in the command line interface (CLI).
    
    Args:
        runner (Runner): A testing utility to invoke the CLI commands.
    
    Returns:
        None: This function asserts the output and exit code of the command invocation.
    """
    result = runner.invoke(cli, ["--list"])
    assert result.exit_code == 0
    assert (
        result.output.strip()
        == """\
AutoFix
DependencyUpgrade
GenerateDocstring
GenerateREADME
GenerateUnitTests
PRReview
ResolveIssue"""
    )


def test_config_list_option_callback(runner, config_dir, patchflow_file):
    """Tests the behavior of the list option in the configuration callback for the CLI.
    
    Args:
        runner (obj): An instance of the test runner that invokes the CLI commands.
        config_dir (Path): The directory path where the configuration files are located.
        patchflow_file (File): The file that serves as a reference for the patchflow name.
    
    Returns:
        None: This function does not return a value; it performs assertions on the CLI output.
    """
    filename = patchflow_file.name
    name_without_ext = filename.replace(patchflow_file.suffix, "")
    result = runner.invoke(cli, ["--list", "--config", str(config_dir)])
    assert result.exit_code == 0
    assert (
        result.output.strip()
        == f"""\
AutoFix
DependencyUpgrade
GenerateDocstring
GenerateREADME
GenerateUnitTests
PRReview
ResolveIssue
{name_without_ext}"""
    )


def test_cli_success(runner, config_dir, patchflow_file):
    """Tests the command-line interface (CLI) for successful execution of the 'noop' command.
    
    Args:
        runner (object): The test runner used to invoke the CLI command.
        config_dir (Path): The directory path for the configuration files.
        patchflow_file (Path): The file path where the 'noop' class code will be written.
    
    Returns:
        None: This function does not return a value, but asserts that the CLI invocation is successful.
    """
    code = """\
class noop:
    def __init__(self, inputs):
        pass
    def run(self):
        return dict(test='test')
"""
    patchflow_file.write_text(code)

    result = runner.invoke(cli, ["noop", "--config", str(config_dir)])

    assert result.exit_code == 0


def test_cli_failure(runner):
    """Tests the command line interface (CLI) for handling failure when provided with a nonexistent configuration file.
    
    Args:
        runner (Fixture): A pytest fixture that provides a way to invoke the CLI commands.
    
    Returns:
        None: This function does not return a value but asserts the exit code of the command.
    """
    result = runner.invoke(cli, ["noop", "--config", "nonexistent"])
    assert result.exit_code == 2


def test_default_find_module():
    # Try to import the module
    """Tests the default behavior of the find_patchflow function to ensure that it
    successfully imports the specified module and matches the expected type.
    
    Args:
        None
    
    Returns:
        None: This function does not return a value but will raise an AssertionError
        if the expected conditions are not met.
    """
    patchflow = find_patchflow(["patchwork.patchflows"], "AutoFix")

    # Check the output
    assert isinstance(patchflow, type)
    assert patchflow.__name__ == "AutoFix"


def test_config_find_module(patchflow_file):
    """Test the functionality of finding a module in a Patchflow file.
    
    Args:
        patchflow_file (Path): The path to the file where the test code is written.
    
    Returns:
        None: This function does not return a value; it only asserts conditions.
    """
    code = """\
class noop:
    def __init__(self, inputs):
        pass
    def run(self):
        return dict(test='test')
"""
    patchflow_file.write_text(code)
    patchflow = find_patchflow([str(patchflow_file.resolve()), "patchwork.patchflows"], "noop")

    # Check the output
    assert isinstance(patchflow, type)
    assert patchflow.__name__ == "noop"
