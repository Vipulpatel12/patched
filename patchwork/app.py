from __future__ import annotations

import importlib
import importlib.util
import json
import signal
import traceback
from collections import deque
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import click
import yaml
from click import echo
from typing_extensions import Iterable

from patchwork.common.client.patched import PatchedClient
from patchwork.common.constants import PROMPT_TEMPLATE_FILE_KEY
from patchwork.logger import init_cli_logger, logger

_DATA_FORMAT_MAPPING = {
    "yaml": yaml.dump,
    "json": json.dumps,
}

_CONFIG_NAME = "config.yml"
_PROMPT_NAME = "prompt.json"
_PATCHFLOW_MODULE_NAME = "patchwork.patchflows"


def _get_patchflow_names(base_path: Path | str | None) -> Iterable[str]:
    """Retrieve patchflow names from a specified directory path.
    
    Args:
        base_path (Path | str | None): The path to the directory from which to retrieve the patchflow names. 
                                         Can be a Path object, a string representing the path, or None.
    
    Returns:
        Iterable[str]: A sorted list of patchflow names derived from subdirectories that contain a corresponding 
                       Python file named '<subdirectory_name>.py'.
    """
    names = []
    if base_path is None:
        return names

    base_path = Path(base_path)
    if not base_path.is_dir():
        return names

    for path in base_path.iterdir():
        if path.is_dir() and (path / f"{path.name}.py").is_file():
            names.append(path.name)
    return sorted(names)


def list_option_callback(ctx: click.Context, param: click.Parameter, value: str | None) -> None:
    """Handles the callback for listing available patchflow options.
    
    This function is designed to collect and display the names of available patchflows
    from specified directories based on user input.
    
    Args:
        ctx click.Context: The context object containing information about the execution state and configuration.
        param click.Parameter: The parameter object associated with the callback.
        value str | None: The input value provided by the user; if None or empty, the function will exit early.
    
    Returns:
        None: This function does not return a value, but it will print the patchflow names and exit the program.
    """
    if not value or ctx.resilient_parsing:
        return

    patchflows = []
    default_path = Path(__file__).parent / "patchflows"
    patchflows.extend(_get_patchflow_names(default_path))

    config_path = ctx.params.get("config")
    patchflows.extend(_get_patchflow_names(config_path))

    echo("\n".join(patchflows), color=ctx.color)
    ctx.exit()


def find_patchflow(possible_module_paths: Iterable[str], patchflow: str) -> Any | None:
    """Attempts to find and load a specified patchflow from a list of possible module paths.
    
    Args:
        possible_module_paths Iterable[str]: An iterable of strings representing paths to potential modules or files.
        patchflow str: The name of the patchflow to be located within the specified modules.
    
    Returns:
        Any | None: The found patchflow object if successful; otherwise, returns None.
    """
    for module_path in possible_module_paths:
        try:
            spec = importlib.util.spec_from_file_location("custom_module", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.info(f'Patchflow `{patchflow}` loaded from "{module_path}"')
            return getattr(module, patchflow)
        except AttributeError:
            logger.debug(f"Patchflow {patchflow} not found in {module_path}")
        except Exception:
            logger.debug(f"Patchflow {patchflow} not found as a file/directory in {module_path}")

        try:
            module = importlib.import_module(module_path)
            logger.info(f"Patchflow {patchflow} loaded from {module_path}")
            return getattr(module, patchflow)
        except ModuleNotFoundError:
            logger.debug(f"Patchflow {patchflow} not found as a module in {module_path}")
        except AttributeError:
            logger.debug(f"Patchflow {patchflow} not found in {module_path}")

    return None


def setup_cli():
    """Sets up the command-line interface (CLI) by configuring signal handling.
    
    This function registers a signal handler for SIGINT (interrupt signal) 
    that logs a message indicating that the signal was received and then exits 
    the program with a status code of 1.
    
    Args:
        None
    
    Returns:
        None
    """
    def sigint_handler(signum, frame):
        """Handles the SIGINT signal.
        
        This function is a signal handler that gets called when a SIGINT signal is received. It logs a message indicating that a SIGINT was received and then exits the program with a status code of 1.
        
        Args:
            signum (int): The signal number that was received.
            frame (signal frame): The current stack frame when the signal was received.
        
        Returns:
            None
        """
        logger.info("Received SIGINT, exiting")
        exit(1)

    signal.signal(signal.SIGINT, sigint_handler)


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.version_option(message="%(version)s", package_name="patchwork-cli")
@click.help_option("-h", "--help")
@click.option(
    "--config",
    is_eager=True,
    type=click.Path(exists=True, dir_okay=True, resolve_path=True, file_okay=True),
    help="Path to the configurations folder, see https://github.com/patched-codes/patchwork-configs for examples.",
)
@click.option(
    "-l",
    "--list",
    is_flag=True,
    expose_value=False,
    callback=list_option_callback,
    help="Show a list of available patchflows, see https://docs.patched.codes/patchflows/patchflows for details.",
)
@click.option(
    "--log",
    hidden=True,
    default="INFO",
    type=click.Choice(
        [
            "CRITICAL",
            "FATAL",
            "ERROR",
            "WARNING",
            "WARN",
            "INFO",
            "DEBUG",
            "TRACE",
        ],
        case_sensitive=False,
    ),
    is_eager=True,
)
@click.argument("patchflow", nargs=1, required=True)
@click.argument("opts", nargs=-1, type=click.UNPROCESSED, required=False)
@click.option(
    "--output",
    type=click.Path(exists=False, resolve_path=True, writable=True),
    help="Path to the output file which contains the state after the patchflow finishes.",
)
@click.option(
    "data_format", "--format", type=click.Choice(["yaml", "json"]), default="json", help="Format of the output file."
)
@click.option("patched_api_key", "--patched_api_key", help="API key to use with the patched.codes service.")
@click.option("disable_telemetry", "--disable_telemetry", is_flag=True, help="Disable telemetry.", default=False)
@click.option("debug", "--debug", is_flag=True, help="Enable debug mode.", default=False)
def cli(
    log: str,
    patchflow: str,
    opts: list[str],
    config: str | None,
    output: str | None,
    data_format: str,
    patched_api_key: str | None,
    disable_telemetry: bool,
    debug: bool,
):
    """Executes a command-line interface (CLI) for the Patchwork tool, initializing logging and processing user inputs for a specified patchflow.
    
    Args:
        log (str): Path to the log file for recording the execution processes.
        patchflow (str): The name of the patchflow to execute, which may optionally include the module path.
        opts (list[str]): List of options provided by the user, which can include key-value pairs.
        config (str | None): Path to the configuration file or directory; if None, defaults are used.
        output (str | None): Path to the output file where results will be written; if None, output is not saved.
        data_format (str): The format in which to serialize the output data; supported formats include JSON.
        patched_api_key (str | None): An optional API key for the patched client; if None, defaults are used.
        disable_telemetry (bool): Flag to disable telemetry data transmission; if True, telemetry is not sent.
        debug (bool): Flag to enable debug mode, providing additional logging output during execution.
    
    Returns:
        None: This function does not return a value; it performs operations directly related to CLI functionality.
    """
    setup_cli()

    init_cli_logger(log)

    if "::" in patchflow:
        module_path, _, patchflow_name = patchflow.partition("::")
    else:
        patchflow_name = patchflow
        module_path = _PATCHFLOW_MODULE_NAME

    possbile_module_paths = deque((module_path,))

    panel = logger.panel("Initializing Patchwork CLI") if debug else nullcontext()

    with panel:
        inputs = {}
        if patched_api_key is not None:
            inputs["patched_api_key"] = patched_api_key

        if config is not None:
            logger.info(f"Using given config value: {config}")
            config_path = Path(config)
            if config_path.is_file():
                inputs = yaml.safe_load(config_path.read_text()) or {}
                logger.info(f"Input values loaded from {config}")
            elif config_path.is_dir():
                patchwork_path = config_path / patchflow_name

                patchwork_python_path = patchwork_path / f"{patchflow_name}.py"
                if patchwork_python_path.is_file():
                    possbile_module_paths.appendleft(str(patchwork_python_path.resolve()))

                patchwork_config_path = patchwork_path / _CONFIG_NAME
                if patchwork_config_path.is_file():
                    inputs = yaml.safe_load(patchwork_config_path.read_text()) or {}
                    logger.info(f"Input values loaded from {patchwork_config_path}")
                else:
                    logger.debug(
                        f'Config file "{patchwork_config_path}" not found from directory {config}, using default config'
                    )

                patchwork_prompt_path = patchwork_path / _PROMPT_NAME
                if patchwork_prompt_path.is_file():
                    inputs[PROMPT_TEMPLATE_FILE_KEY] = patchwork_prompt_path
                    logger.info(f"Prompt template loaded from {patchwork_prompt_path}")
                else:
                    logger.debug(
                        f'Prompt file "{patchwork_prompt_path}" not found from directory {config}, using default prompt'
                    )
            else:
                logger.error(f"Config path {config} is neither a file nor a directory")
                exit(1)

        if debug:
            inputs["debug"] = True

        patchflow_class = find_patchflow(possbile_module_paths, patchflow_name)
        if patchflow_class is None:
            logger.error(f"Patchflow {patchflow_name} not found in {possbile_module_paths}")
            exit(1)

    for opt in opts:
        key, equal_sign, value = opt.partition("=")
        key = key.lstrip("-")

        if equal_sign == "":
            # treat --key as a flag
            inputs[key] = True
        else:
            # treat --key=value as a key-value pair
            inputs[key] = value

    patchflow_panel = nullcontext() if debug else logger.panel(f"Patchflow {patchflow} inputs")

    with patchflow_panel as _:
        if debug is True:
            logger.info("DEBUGGING ENABLED. INPUTS WILL BE SHOWN BEFORE EACH STEP BEFORE PROCEEDING TO RUN IT.")
        try:
            patched = PatchedClient(inputs.get("patched_api_key"))
            if not disable_telemetry:
                patched.send_public_telemetry(patchflow_name, inputs)

            with patched.patched_telemetry(patchflow_name, {}):
                patchflow_instance = patchflow_class(inputs)
                patchflow_instance.run()
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Error running patchflow {patchflow}: {e}")
            exit(1)

    if output is not None:
        serialize = _DATA_FORMAT_MAPPING.get(data_format, json.dumps)
        with open(output, "w") as file:
            file.write(serialize(inputs))


if __name__ == "__main__":
    cli()
