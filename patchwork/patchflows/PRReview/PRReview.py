import json
from pathlib import Path

import yaml

from patchwork.common.utils.progress_bar import PatchflowProgressBar
from patchwork.common.utils.step_typing import validate_steps_with_inputs
from patchwork.step import Step
from patchwork.steps import (
    LLM,
    CallLLM,
    CreatePRComment,
    ExtractModelResponse,
    PreparePR,
    PreparePrompt,
    ReadPRDiffs,
)

_DEFAULT_PROMPT_JSON = Path(__file__).parent / "pr_review_prompt.json"
_DEFAULT_INPUT_FILE = Path(__file__).parent / "defaults.yml"


_NONE = "none"
_SHORT = "short"
_LONG = "long"
_SUMMARY_LEVEL = {
    _NONE: 0,
    _SHORT: 1,
    _LONG: 2,
}


class PRReview(Step):
    def __init__(self, inputs: dict):
        """Initializes the class by registering necessary steps for the Patchflow progress and setting up inputs.
        
        Args:
            inputs dict: A dictionary containing inputs to be used for initialization.
        
        Returns:
            None: The constructor does not return any value but initializes the object state.
        """ 
        PatchflowProgressBar(self).register_steps(
            CallLLM,
            CreatePRComment,
            ExtractModelResponse,
            PreparePR,
            PreparePrompt,
            ReadPRDiffs,
        )
        final_inputs = yaml.safe_load(_DEFAULT_INPUT_FILE.read_text())
        final_inputs.update(inputs)

        if "prompt_template_file" not in final_inputs.keys():
            final_inputs["prompt_template_file"] = _DEFAULT_PROMPT_JSON

        diff_summary = final_inputs.get("diff_summary", _LONG)
        if diff_summary.lower() not in _SUMMARY_LEVEL.keys():
            raise ValueError(f"Invalid diff_summary, accepted diff_summary values: {_SUMMARY_LEVEL.keys()}")
        self.verbosity = _SUMMARY_LEVEL[diff_summary.lower()]

        self.is_suggestion_required = bool(final_inputs.get("diff_suggestion"))

        validate_steps_with_inputs(
            set(final_inputs.keys()).union(
                {
                    "prompt_id",
                    "prompt_values",
                    "modified_code_files",
                    "pr_comment",
                }
            ),
            ReadPRDiffs,
            LLM,
            PreparePR,
            CreatePRComment,
        )

        self.inputs = final_inputs

    def run(self) -> dict:
        """Executes the process of generating pull request (PR) summaries and comments based on the provided inputs.
        
        This method gathers input differences, generates suggestions or summaries using a language model, and prepares the necessary data for creating a PR comment. The verbosity level determines the extent of the output.
        
        Args:
            self: The instance of the class which contains the inputs and verbosity level.
        
        Returns:
            dict: A dictionary containing the final inputs, including generated PR header and modified code files.
        """
        if self.verbosity == _SUMMARY_LEVEL[_NONE]:
            return dict()

        outputs = ReadPRDiffs(self.inputs).run()
        self.inputs["prompt_values"] = outputs["diffs"]

        outputs = LLM(
            dict(
                prompt_id="diffreview-suggestion" if self.is_suggestion_required else "diffreview",
                model_response_format=dict(type="json_object"),
                **self.inputs,
            )
        ).run()
        self.inputs.update(outputs)

        summaries = []
        for raw_response, prompt_values in zip(self.inputs["openai_responses"], self.inputs["prompt_values"]):
            response = json.loads(raw_response)
            summary = {}
            if "path" in prompt_values.keys():
                summary["path"] = prompt_values["path"]
            if "review" in response.keys():
                summary["commit_message"] = response["review"]
            if "suggestion" in response.keys():
                summary["patch_message"] = response["suggestion"]
            summaries.append(summary)

        header = ""
        if self.verbosity > _SUMMARY_LEVEL[_SHORT]:
            filtered_summaries = [
                str(summary["commit_message"]) for summary in summaries if summary.get("commit_message")
            ]
            self.inputs["prompt_id"] = "diffreview_summary"
            self.inputs["prompt_values"] = [{"diffreviews": "\n".join(filtered_summaries)}]

            outputs = PreparePrompt(self.inputs).run()
            self.inputs.update(outputs)
            outputs = CallLLM(self.inputs).run()
            self.inputs.update(outputs)
            header = self.inputs["openai_responses"][0]

        self.inputs["pr_header"] = header
        self.inputs["modified_code_files"] = summaries
        outputs = PreparePR(self.inputs).run()
        self.inputs.update(outputs)

        self.inputs["pr_comment"] = self.inputs["pr_body"]
        outputs = CreatePRComment(self.inputs).run()
        self.inputs.update(outputs)

        return self.inputs
