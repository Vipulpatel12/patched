from __future__ import annotations

import os
from pathlib import Path

from patchwork.common.context_strategy.languages import PythonLanguage
from patchwork.step import Step
from patchwork.steps.ExtractCodeContexts.ExtractCodeContexts import ExtractCodeContexts


class ExtractCodeMethodForCommentContexts(Step):
    required_keys = {}

    def __init__(self, inputs: dict):
        """Initializes the class instance with the provided input parameters.
        
        Args:
            inputs dict: A dictionary containing the initialization parameters. This must include all required keys as defined in 'required_keys'. 
                         The dictionary may contain additional optional keys: 
                         - "base_path" (str): Specifies the base path; defaults to the current working directory if not provided.
                         - "force_code_contexts" (bool): A flag to force code contexts; defaults to False if not provided.
                         - "allow_overlap_contexts" (bool): A flag to allow overlapping contexts; defaults to True if not provided.
                         - "max_depth" (int): Specifies the maximum depth; defaults to -1 if not provided.
        
        Raises:
            ValueError: If any required keys are missing from the input dictionary.
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.base_path = Path(inputs.get("base_path", os.getcwd()))
        # rethink this, should be one level up and true by default
        self.force_code_contexts = inputs.get("force_code_contexts", False)
        self.allow_overlap_contexts = inputs.get("allow_overlap_contexts", True)
        self.max_depth = int(inputs.get("max_depth", -1))

    def run(self) -> dict:
        """Executes the extraction of code contexts, generating a structured dictionary of file patches.
        
        Args:
            self: Instance of the class containing necessary attributes for execution.
        
        Returns:
            dict: A dictionary containing a list of code contexts that need to be patched, 
                  with each context detailing the file URI, start line, end line, 
                  affected code, and comment format.
        """
        positions_gen = ExtractCodeContexts(
            dict(
                base_path=self.base_path,
                context_grouping="FUNCTION",
                force_code_contexts=self.force_code_contexts,
                allow_overlap_contexts=self.allow_overlap_contexts,
            )
        ).get_positions(max_depth=self.max_depth)

        extracted_code_contexts = []
        for file_path, src, position in positions_gen:
            comment_position = position.meta_positions.get("comment")
            if comment_position is not None:
                start_line = comment_position.start
                end_line = comment_position.end
            elif isinstance(position.language, PythonLanguage) and position.meta_positions.get("body") is not None:
                # if the comment is not found in python functions/methods, we will use the body position
                body_position = position.meta_positions.get("body")
                start_line = body_position.start
                end_line = body_position.start
            else:
                start_line = position.start
                end_line = position.start

            extracted_code_context = dict(
                uri=file_path,
                startLine=start_line,
                endLine=end_line,
                affectedCode="".join(src[position.start : position.end]),
                commentFormat=position.language.docstring_format,
            )
            extracted_code_contexts.append(extracted_code_context)

        return dict(
            files_to_patch=extracted_code_contexts,
        )
