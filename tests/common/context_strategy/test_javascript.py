import pytest

from patchwork.common.context_strategy.javascript import (
    JavascriptBlockStrategy,
    JavascriptClassStrategy,
    JavascriptFunctionStrategy,
    JsxBlockStrategy,
    JsxClassStrategy,
    JsxFunctionStrategy,
)

example_js_lines = [
    'import React from "react";\n',  # 0
    "export default class App extends React.Component {\n",  # 1
    "  state = {\n",  # 2
    "    total: null,\n",  # 3
    "    next: null,\n",  # 4
    "    operation: null,\n",  # 5
    "  };\n",  # 6
    "\n",  # 7
    "  /** @param {string} buttonName */\n",  # 8
    "  handleClick = buttonName => {\n",  # 9
    "    this.setState(calculate(this.state, buttonName));\n",  # 10
    "  };\n",  # 11
    "\n",  # 12
    "  handleClick = function(buttonName) {\n",  # 13
    "    this.setState(calculate(this.state, buttonName));\n",  # 14
    "  };\n",  # 15
    "\n",  # 16
    "  render() {\n",  # 17
    "    return (\n",  # 18
    '      <div className="component-app">\n',  # 19
    "      </div>\n",  # 20
    "    );\n",  # 21
    "  }\n",  # 22
    "}\n",  # 23
    "export function abc(a) {\n",  # 24
    "    return 1;\n",  # 25
    "}\n",  # 26
    "function def(a) {\n",  # 27
    "    return 1;\n",  # 28
    "}\n",  # 29
]


@pytest.mark.parametrize(
    "strategy, expected_context_count, lines",
    [
        (JavascriptClassStrategy(), 1, example_js_lines),
        (JavascriptFunctionStrategy(), 4, example_js_lines),
        (JavascriptBlockStrategy(), 5, example_js_lines),
        (JsxClassStrategy(), 1, example_js_lines),
        (JsxFunctionStrategy(), 4, example_js_lines),
        (JsxBlockStrategy(), 5, example_js_lines),
    ],
)
def test_js_strategy_contexts(strategy, expected_context_count, lines):
    """Tests the behavior of a given strategy's context extraction method.
    
    Args:
        strategy (Strategy): An instance of a strategy class that implements the context extraction method.
        expected_context_count (int): The expected number of contexts to be returned by the strategy.
        lines (list): A list of lines from which contexts will be extracted.
    
    Returns:
        None: This function does not return a value; it asserts the expected condition.
    """
    contexts = strategy.get_contexts(lines)
    assert len(contexts) == expected_context_count


@pytest.mark.parametrize(
    "strategy, line_range, lines",
    [
        (JavascriptClassStrategy(), (0, 1), example_js_lines),
        (JavascriptFunctionStrategy(), (12, 13), example_js_lines),
        (JavascriptBlockStrategy(), (0, 1), example_js_lines),
        (JsxClassStrategy(), (0, 1), example_js_lines),
        (JsxFunctionStrategy(), (12, 13), example_js_lines),
        (JsxBlockStrategy(), (0, 1), example_js_lines),
    ],
)
def test_js_strategy_line_context_misses(strategy, line_range, lines):
    """Tests the behavior of the JavaScript strategy when the context for a specific line range is missed.
    
    Args:
        strategy (Strategy): An instance of the strategy being tested, which provides the method to get context indexes.
        line_range (tuple): A tuple containing the start and end indices of the line range to be checked.
        lines (list): A list of lines to be examined for context.
    
    Returns:
        None: This function asserts if the context indexes returned are None, indicating a miss.
    """
    position = strategy.get_context_indexes(lines, line_range[0], line_range[1])
    assert position is None


@pytest.mark.parametrize(
    "strategy, line_range, expected_range, lines",
    [
        (JavascriptClassStrategy(), (11, 12), (1, 24), example_js_lines),
        (JavascriptFunctionStrategy(), (11, 12), (9, 12), example_js_lines),
        (JavascriptBlockStrategy(), (11, 12), (9, 12), example_js_lines),
        (JsxClassStrategy(), (11, 12), (1, 24), example_js_lines),
        (JsxFunctionStrategy(), (11, 12), (9, 12), example_js_lines),
        (JsxBlockStrategy(), (11, 12), (9, 12), example_js_lines),
    ],
)
def test_js_strategy_line_context(strategy, line_range, expected_range, lines):
    """Tests the functionality of the 'get_context_indexes' method of a given strategy.
    
    Args:
        strategy (object): The strategy object that contains the method to be tested.
        line_range (tuple): A tuple containing the start and end indexes of the lines to be processed.
        expected_range (tuple): A tuple containing the expected start and end indexes returned by the method.
        lines (list): A list of lines to be examined by the strategy method.
    
    Returns:
        None: Asserts that the actual start and end indexes match the expected values without returning any value.
    """
    expected_start, expected_end = expected_range
    position = strategy.get_context_indexes(lines, line_range[0], line_range[1])
    assert position.start == expected_start
    assert position.end == expected_end
