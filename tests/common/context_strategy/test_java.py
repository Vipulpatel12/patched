import pytest

from patchwork.common.context_strategy.java import (
    JavaBlockStrategy,
    JavaClassStrategy,
    JavaMethodStrategy,
)

example_java_lines = [
    "package com.example;\n",  # 0
    "\n",  # 1
    "import java.util.ArrayList;\n",  # 2
    "import java.util.List;\n",  # 3
    "import java.util.Map;\n",  # 4
    "\n",  # 5
    "public class A {\n",  # 6
    "    /** comment  */\n",  # 7
    "    public static void main(String[] args) {\n",  # 8
    '        System.out.println("Hello, World!");\n',  # 9
    "    }\n",  # 10
    "}\n",  # 11
]


@pytest.mark.parametrize(
    "strategy, expected_range",
    [(JavaClassStrategy(), (6, 12)), (JavaMethodStrategy(), (8, 11)), (JavaBlockStrategy(), (8, 11))],
)
def test_java_strategy(strategy, expected_range):
    """Tests the Java strategy's context index retrieval by comparing the actual output 
       with the expected start and end positions.
    
    Args:
        strategy (JavaStrategy): The Java strategy instance used to retrieve context indexes.
        expected_range (tuple): A tuple containing the expected start and end indices.
    
    Returns:
        None: This function asserts the correctness of the retrieved index positions.
    """
    expected_start, expected_end = expected_range
    position = strategy.get_context_indexes(example_java_lines, 8, 9)
    assert position.start == expected_start
    assert position.end == expected_end
