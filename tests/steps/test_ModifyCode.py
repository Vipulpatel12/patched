import json

import pytest

from patchwork.steps.ModifyCode.ModifyCode import (
    ModifyCode,
    handle_indent,
    replace_code_in_file,
    save_file_contents,
)


def test_save_file_contents(tmp_path):
    """Tests the functionality of the save_file_contents function.
    
    Args:
        tmp_path Path: A temporary directory path provided by pytest for testing.
    
    Returns:
        None: This is a test function and does not return any value.
    """
    file_path = tmp_path / "test.txt"
    content = "Hello, World!"
    save_file_contents(str(file_path), content)
    assert file_path.read_text() == content


@pytest.mark.parametrize(
    "src,target,expected",
    [
        ([], [], []),
        (["line 1"], ["line 1"], ["line 1"]),
        (["line 1", "line 2"], ["line 1", "line 2"], ["line 1", "line 2"]),
        (["  def foo():", "    pass"], ["  def bar():", "    pass"], ["  def bar():", "    pass"]),
        (["  def foo():", "    pass"], ["def bar():", "  pass"], ["  def bar():", "    pass"]),
        (["\tdef foo():", "\t\tpass"], ["def bar():", "\tpass"], ["\tdef bar():", "\t\tpass"]),
    ],
)
def test_handle_indent(src, target, expected):
    """Tests the handle_indent function to ensure it produces the expected indentation output.
    
    Args:
        src (str): The source string to be indented.
        target (str): The target string to receive the indentation.
        expected (str): The expected result after indentation.
    
    Returns:
        None: This function does not return a value, but asserts that the output is as expected.
    """
    indented_target = handle_indent(src, target, 0, 999)
    assert indented_target == expected


def test_replace_code_in_file(tmp_path):
    """Tests the functionality of replacing code in a specified range of lines in a file.
    
    Args:
        tmp_path (pathlib.Path): A temporary directory unique to the test invocation.
    
    Returns:
        None: This function does not return a value. It asserts that the content of the file 
        after replacement matches the expected output.
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("line 1\nline 2\nline 3")
    start_line = 1
    end_line = 3
    new_code = "new line 1\nnew line 2"
    replace_code_in_file(str(file_path), start_line, end_line, new_code)
    assert file_path.read_text() == "line 1\nnew line 1\nnew line 2\n"


def test_modify_code_init():
    """Test the initialization of the ModifyCode class.
    
    This function initializes the ModifyCode class with specific input parameters
    and asserts that the instance variables are set correctly.
    
    Args:
        None
    
    Returns:
        None
    """
    inputs = {
        "files_to_patch": [{"uri": "path/to/uri", "startLine": 1, "endLine": 2}],
        "extracted_responses": [{"uri": "path/to/uri", "startLine": 1, "endLine": 2, "patch": "new_code"}],
    }
    modify_code = ModifyCode(inputs)
    assert modify_code.files_to_patch == [{"uri": "path/to/uri", "startLine": 1, "endLine": 2}]
    assert modify_code.extracted_responses == [
        {"uri": "path/to/uri", "startLine": 1, "endLine": 2, "patch": "new_code"}
    ]


def test_modify_code_run(tmp_path):
    """Tests the functionality of the ModifyCode class to ensure that code modifications are applied correctly to the specified lines in a file.
    
    Args:
        tmp_path Path: A temporary directory path provided by pytest for creating test files.
    
    Returns:
        None
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("line 1\nline 2\nline 3")

    code_snippets_path = tmp_path / "code.json"
    with open(code_snippets_path, "w") as f:
        json.dump([{"uri": str(file_path), "startLine": 1, "endLine": 2}], f)

    inputs = {
        "files_to_patch": [{"uri": str(file_path), "startLine": 1, "endLine": 2}],
        "extracted_responses": [{"patch": "new_code"}],
    }
    modify_code = ModifyCode(inputs)
    result = modify_code.run()
    assert result.get("modified_code_files") is not None
    assert len(result["modified_code_files"]) == 1


def test_modify_code_none_edit(tmp_path):
    """Tests the ModifyCode class's ability to handle a case where no modifications are made to the code.
    
    This test creates a temporary text file containing multiple lines and a JSON file describing which lines are to be modified. It simulates a scenario where no patch is provided, and verifies that the resulting modified code files list is empty.
    
    Args:
        tmp_path (Path): A temporary directory path used for creating test files.
    
    Returns:
        None: This function does not return any value.
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("line 1\nline 2\nline 3")

    code_snippets_path = tmp_path / "code.json"
    with open(code_snippets_path, "w") as f:
        json.dump([{"uri": str(file_path), "startLine": 1, "endLine": 2}], f)

    inputs = {
        "files_to_patch": [{"uri": str(file_path), "startLine": 1, "endLine": 2}],
        "extracted_responses": [{"patch": None}],
    }
    modify_code = ModifyCode(inputs)
    result = modify_code.run()
    assert result.get("modified_code_files") is not None
    assert len(result["modified_code_files"]) == 0
