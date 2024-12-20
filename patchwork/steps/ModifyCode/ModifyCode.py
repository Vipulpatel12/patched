from __future__ import annotations

from pathlib import Path

from patchwork.step import Step, StepStatus


def save_file_contents(file_path, content):
    """Utility function to save content to a file."""
    with open(file_path, "w") as file:
        file.write(content)


def handle_indent(src: list[str], target: list[str], start: int, end: int) -> list[str]:
    """Adjusts the indentation of the target lines based on the indentation of the source lines.
    
    Args:
        src (list[str]): A list of source code lines from which to inherit indentation.
        target (list[str]): A list of target code lines to adjust the indentation for.
        start (int): The starting index in the source list to look for indentation.
        end (int): The ending index in the source list to look for indentation.
    
    Returns:
        list[str]: A new list of target lines with adjusted indentation.
    """
    if len(target) < 1:
        return target

    if start == end:
        end = start + 1

    first_src_line = next((line for line in src[start:end] if line.strip() != ""), "")
    src_indent_count = len(first_src_line) - len(first_src_line.lstrip())
    first_target_line = next((line for line in target if line.strip() != ""), "")
    target_indent_count = len(first_target_line) - len(first_target_line.lstrip())
    indent_diff = src_indent_count - target_indent_count

    indent = ""
    if indent_diff > 0:
        indent_unit = first_src_line[0]
        indent = indent_unit * indent_diff

    return [indent + line for line in target]


def replace_code_in_file(
    file_path: str,
    start_line: int | None,
    end_line: int | None,
    new_code: str,
) -> None:
    """Replaces specified lines in a file with new code.
    
    Args:
        file_path str: The path of the file to modify.
        start_line int | None: The starting line index to replace, or None if no replacement should occur.
        end_line int | None: The ending line index to replace, or None if no replacement should occur.
        new_code str: The new code that will be inserted into the specified lines.
    
    Returns:
        None: This function does not return a value. It modifies the file in place.
    """
    path = Path(file_path)
    new_code_lines = new_code.splitlines(keepends=True)
    if len(new_code_lines) > 0 and not new_code_lines[-1].endswith("\n"):
        new_code_lines[-1] += "\n"

    if path.exists() and start_line is not None and end_line is not None:
        """Replaces specified lines in a file with new code."""
        text = path.read_text()

        lines = text.splitlines(keepends=True)

        # Insert the new code at the start line after converting it into a list of lines
        lines[start_line:end_line] = handle_indent(lines, new_code_lines, start_line, end_line)
    else:
        lines = new_code_lines

    # Save the modified contents back to the file
    save_file_contents(file_path, "".join(lines))


class ModifyCode(Step):
    UPDATED_SNIPPETS_KEY = "extracted_responses"
    FILES_TO_PATCH = "files_to_patch"
    required_keys = {FILES_TO_PATCH, UPDATED_SNIPPETS_KEY}

    def __init__(self, inputs: dict):
        """Initializes the class with the provided input dictionary and validates the presence of required keys.
        
        Args:
            inputs dict: A dictionary containing required inputs needed for initialization.
        
        Raises:
            ValueError: If any of the required keys are missing from the input dictionary.
        
        Attributes:
            files_to_patch: The value associated with the key FILES_TO_PATCH from the input dictionary.
            extracted_responses: The value associated with the key UPDATED_SNIPPETS_KEY from the input dictionary.
        """
        super().__init__(inputs)
        if not all(key in inputs.keys() for key in self.required_keys):
            raise ValueError(f'Missing required data: "{self.required_keys}"')

        self.files_to_patch = inputs[self.FILES_TO_PATCH]
        self.extracted_responses = inputs[self.UPDATED_SNIPPETS_KEY]

    def run(self) -> dict:
        """Executes the process of modifying code files based on extracted responses.
        
        This method sorts the provided code snippets along with their respective 
        extracted responses by their start line in descending order. It applies 
        the modifications to the specified files and returns a summary of the 
        modified files.
        
        Args:
            self: The instance of the class containing the method.
        
        Returns:
            dict: A dictionary containing a list of modified code files, where 
                  each entry includes the path, start line, end line, and additional 
                  details from the extracted response.
        """
        modified_code_files = []
        sorted_list = sorted(
            zip(self.files_to_patch, self.extracted_responses), key=lambda x: x[0].get("startLine", -1), reverse=True
        )
        if len(sorted_list) == 0:
            self.set_status(StepStatus.SKIPPED, "No code snippets to modify.")
            return dict(modified_code_files=[])

        for code_snippet, extracted_response in sorted_list:
            uri = code_snippet.get("uri")
            start_line = code_snippet.get("startLine")
            end_line = code_snippet.get("endLine")
            new_code = extracted_response.get("patch")

            if new_code is None:
                continue
            
            replace_code_in_file(uri, start_line, end_line, new_code)
            modified_code_file = dict(path=uri, start_line=start_line, end_line=end_line, **extracted_response)
            modified_code_files.append(modified_code_file)

        return dict(modified_code_files=modified_code_files)
