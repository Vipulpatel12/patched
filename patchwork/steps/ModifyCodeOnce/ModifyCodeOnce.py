from __future__ import annotations

from patchwork.step import Step, StepStatus
from patchwork.steps import ModifyCode
from patchwork.steps.ModifyCodeOnce.typed import (
    ModifyCodeOnceInputs,
    ModifyCodeOnceOutputs,
)


class ModifyCodeOnce(Step, input_class=ModifyCodeOnceInputs, output_class=ModifyCodeOnceOutputs):
    def __init__(self, inputs: dict):
        """Initializes an instance of the class.
        
        Args:
            inputs dict: A dictionary containing initialization parameters. 
                Expected keys include "file_path", "start_line", "end_line", 
                and "new_code".
        
        Returns:
            None: This method does not return a value.
        """
        super().__init__(inputs)
        self.file_path = inputs["file_path"]
        self.start_line = inputs.get("start_line")
        self.end_line = inputs.get("end_line")
        self.patch = inputs.get("new_code")

    def run(self) -> dict:
        """Executes the patching process by modifying code based on the provided patch information.
        
        Args:
            self.patch (str or None): The patch to be applied. If None, the method will skip execution.
        
        Returns:
            dict: A dictionary containing the modified code files or an empty dictionary if no modifications were made.
        """
        if self.patch is None:
            self.set_status(StepStatus.SKIPPED, "No patch provided")
            return {}

        modify_code = ModifyCode(
            {
                "files_to_patch": [
                    dict(
                        uri=self.file_path,
                        startLine=self.start_line,
                        endLine=self.end_line,
                    )
                ],
                "extracted_responses": [
                    dict(
                        patch=self.patch,
                    )
                ],
            }
        )
        modified_code_files = modify_code.run()
        return modified_code_files.get("modified_code_files", [{}])[0]
