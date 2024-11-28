import os
from pathlib import Path

import pytest

from patchwork.steps.ExtractCode.ExtractCode import ExtractCode, Severity

_DEFAULT_SARIF_FILE_NAME = "sarif_file.sarif"


@pytest.fixture
def extract_code_instance(tmp_path):
    """Extracts the code instance from a specified temporary path and yields an ExtractCode instance.
    
    Args:
        tmp_path (Path): The temporary path where the test file will be created and analyzed.
    
    Returns:
        ExtractCode: An instance of ExtractCode initialized with the specified inputs based on test file data.
    """
    original_dir = Path.cwd()

    os.chdir(tmp_path)

    test_file = tmp_path / "test.py"
    test_file.write_text("print('Hello, world!')")

    inputs = {
        "sarif_values": {
            "runs": [
                {
                    "results": [
                        {
                            "message": {"text": "Error message"},
                            "ruleId": "1",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": str(test_file)},
                                        "region": {"startLine": 1, "endLine": 1},
                                    }
                                }
                            ],
                        }
                    ],
                    "tool": {"driver": {"rules": [{"id": "1", "defaultConfiguration": {"level": "high"}}]}},
                }
            ],
        },
        "context_size": 1000,
        "vulnerability_limit": 10,
        "severity": "HIGH",
    }
    yield ExtractCode(inputs)
    os.chdir(original_dir)


def test_extract_code_init(extract_code_instance):
    """Test the initialization of the extract_code_instance.
    
    This test validates that the extract_code_instance is initialized with the correct default values for context length, vulnerability limit, and severity threshold.
    
    Args:
        extract_code_instance (ExtractCode): An instance of the ExtractCode class to test.
    
    Returns:
        None: This function does not return a value; it asserts conditions.
    """
    assert extract_code_instance.context_length == 1000
    assert extract_code_instance.vulnerability_limit == 10
    assert extract_code_instance.severity_threshold == Severity.HIGH


def test_extract_code_run(extract_code_instance, tmp_path):
    # Run the extract code step
    """Test the behavior of the extract_code_instance's run method.
    
    This test verifies that the run method of the extract_code_instance returns
    the expected structure and content when executed. It checks for the presence
    of the key "files_to_patch" and validates that the corresponding output data
    matches the expected format and values.
    
    Args:
        extract_code_instance (ExtractCode): An instance of the ExtractCode class
            used to perform the code extraction.
        tmp_path (Path): A temporary directory path provided by pytest for file
            operations during testing.
    
    Returns:
        None: This function does not return a value; it asserts conditions to validate
        the output of the extract_code_instance.run() method.
    """
    result = extract_code_instance.run()

    assert result.keys() == {"files_to_patch"}
    for output_data in result.values():
        assert len(output_data) == 1
        assert output_data[0]["uri"] == "test.py"
        assert output_data[0]["startLine"] == 0
        assert output_data[0]["endLine"] == 1
        assert output_data[0]["affectedCode"] == "print('Hello, world!')"
        assert output_data[0]["messageText"] == "Issue Description: Error message"


@pytest.fixture
def extract_code_instance_with_fix(tmp_path):
    """Extracts code instances with fixes from specified input values and writes them to a temporary file.
    
    Args:
        tmp_path Path: The temporary directory path where the test file will be created and code is extracted from.
    
    Returns:
        Generator: Yields an instance of ExtractCode initialized with the given input values.
    """
    original_dir = Path.cwd()

    os.chdir(tmp_path)

    test_file = tmp_path / "test.py"
    test_file.write_text("print('Hello, world!')")

    inputs = {
        "sarif_values": {
            "runs": [
                {
                    "results": [
                        {
                            "fixes": [{"description": {"text": "Fix here"}}, {"description": {"text": "Fix there"}}],
                            "message": {"text": "Error message"},
                            "ruleId": "1",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": str(test_file)},
                                        "region": {"startLine": 1, "endLine": 1},
                                    }
                                }
                            ],
                        }
                    ],
                    "tool": {"driver": {"rules": [{"id": "1", "defaultConfiguration": {"level": "high"}}]}},
                }
            ],
        },
        "context_size": 1000,
        "vulnerability_limit": 10,
        "severity": "HIGH",
    }
    yield ExtractCode(inputs)
    os.chdir(original_dir)


def test_extract_code_run_with_fix(extract_code_instance_with_fix, tmp_path):
    # Run the extract code step
    """Test the extraction of code with a provided fix using the extract code instance.
    
    Args:
        extract_code_instance_with_fix (ExtractCode): An instance of ExtractCode configured with fixes.
        tmp_path (Path): A temporary path for file manipulation during the test.
    
    Returns:
        None: This function does not return a value; it asserts the correctness of the result.
    """
    result = extract_code_instance_with_fix.run()

    assert result.keys() == {"files_to_patch"}
    for output_data in result.values():
        assert len(output_data) == 1
        assert output_data[0]["uri"] == "test.py"
        assert output_data[0]["startLine"] == 0
        assert output_data[0]["endLine"] == 1
        assert output_data[0]["affectedCode"] == "print('Hello, world!')"
        assert (
            output_data[0]["messageText"]
            == """\
Issue Description: Error message
Suggested fixes:
- Fix here
- Fix there"""
        )
