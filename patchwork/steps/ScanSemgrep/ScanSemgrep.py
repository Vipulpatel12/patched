import json
import subprocess
from pathlib import Path

from patchwork.common.utils.dependency import import_with_dependency_group
from patchwork.common.utils.input_parsing import parse_to_list
from patchwork.logger import logger
from patchwork.step import Step, StepStatus
from patchwork.steps.ScanSemgrep.typed import ScanSemgrepInputs, ScanSemgrepOutputs


class ScanSemgrep(Step, input_class=ScanSemgrepInputs, output_class=ScanSemgrepOutputs):
    def __init__(self, inputs: dict):
        """Initializes an instance of the class.
        
        This constructor accepts a dictionary of inputs and initializes the instance variables based on the provided data. It retrieves `semgrep_extra_args`, loads SARIF values from a specified file, or directly from the input if available. It also parses paths into a list using defined delimiters.
        
        Args:
            inputs dict: A dictionary containing initialization parameters, including:
                - "semgrep_extra_args" (str): Additional arguments for Semgrep.
                - "sarif_file_path" (str): Path to a SARIF file from which to load values.
                - "sarif_values" (str or dict): SARIF values either as a JSON string or dictionary.
                - "path_key" (str): The key used to identify paths in the inputs (default is "path").
                - "paths" (str): A string of paths, potentially delimited by commas or specified key.
        
        Raises:
            ValueError: If the specified SARIF file does not exist.
        
        Returns:
            None
        """
        super().__init__(inputs)

        self.extra_args = inputs.get("semgrep_extra_args", "")
        sarif_file_path = inputs.get("sarif_file_path")
        if sarif_file_path is not None:
            sarif_file_path = Path(sarif_file_path)
            if not sarif_file_path.is_file():
                raise ValueError(f'Unable to find input file: "{sarif_file_path}"')
            with open(sarif_file_path, "r") as fp:
                self.sarif_values = json.load(fp, strict=False)
        elif inputs.get("sarif_values") is not None:
            sarif_values = inputs.get("sarif_values")
            if isinstance(sarif_values, str):
                sarif_values = json.loads(sarif_values, strict=False)
            self.sarif_values = sarif_values
        else:
            self.sarif_values = None

        path_key = inputs.get("path_key", "path")
        self.paths = parse_to_list(inputs.get("paths", ""), possible_delimiters=[",", None], possible_keys=[path_key])

    def run(self) -> dict:
        """Executes a scan using Semgrep and returns the SARIF output.
        
        This method checks if SARIF values are provided; if so, it returns them directly. 
        If not, it runs the Semgrep command with specified paths and extra arguments, 
        captures its output, and attempts to parse it as JSON. In case of a parsing error, 
        it logs the error and updates the status accordingly.
        
        Args:
            self: The instance of the class containing the method.
        
        Returns:
            dict: A dictionary containing the SARIF values if the scan is successful or 
                  an empty dictionary if the scan fails or SARIF values are not available.
        """
        if self.sarif_values is not None:
            self.set_status(StepStatus.SKIPPED, "Using provided SARIF")
            return dict(sarif_values=self.sarif_values)

        import_with_dependency_group("semgrep")
        cwd = Path.cwd()

        cmd = [
            "semgrep",
            "scan",
            *self.paths,
            *self.extra_args.split(),
            "--sarif",
        ]

        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        try:
            sarif_values = json.loads(p.stdout)
            return dict(sarif_values=sarif_values)
        except json.JSONDecodeError as e:
            logger.debug(f"Error parsing semgrep output: {p.stdout}", e)
            self.set_status(StepStatus.FAILED, f"Error parsing semgrep output")
