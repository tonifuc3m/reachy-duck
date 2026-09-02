"""Tests for the restricted calculator and lexical note search."""

from pathlib import Path

import pytest

from reachy_duck.notes import add_note, search_notes
from reachy_duck.calculator import calculate


def test_calculate_basic_arithmetic() -> None:
    """The calculator supports addition, subtraction, multiplication, and division."""
    assert calculate("23 * 47") == {"expression": "23 * 47", "result": 1081}
    assert calculate("10 - 3 + 1") == {"expression": "10 - 3 + 1", "result": 8}
    assert calculate("9 / 4") == {"expression": "9 / 4", "result": 2.25}


def test_calculate_parentheses_powers_percentages_and_decimals() -> None:
    """Supported operators retain ordinary arithmetic precedence."""
    assert calculate("(12 + 8) / 5")["result"] == 4
    assert calculate("2 ** 8")["result"] == 256
    assert calculate("17 / 100 * 850")["result"] == 144.5
    assert calculate("1.5 + 0.25")["result"] == 1.75
    assert calculate("10 % 3")["result"] == 1


@pytest.mark.parametrize(
    ("expression", "error"),
    [
        ("1 / 0", "Division by zero"),
        ("(1 +", "Malformed expression"),
        ("__import__('os').system('id')", "Unsupported expression"),
        ("variable + 1", "Unsupported expression"),
        ("2 ** 101", "Exponent exceeds maximum size"),
        ("2 ** 100", "Numeric magnitude exceeds maximum"),
        ("1" * 201, "Expression exceeds maximum length"),
    ],
)
def test_calculate_rejects_invalid_unsafe_and_resource_heavy_input(expression: str, error: str) -> None:
    """Unsafe AST nodes and resource-limit violations have concise errors."""
    assert calculate(expression) == {"expression": expression, "error": error}


def test_search_notes_is_case_insensitive_bounded_and_preserves_note_text(tmp_path: Path) -> None:
    """Search returns matching note entry bodies in insertion order."""
    add_note("Add Google Calendar support for recurring events.", instance_path=tmp_path)
    add_note("Buy GROCERIES: milk and bread.", instance_path=tmp_path)
    add_note("Google Calendar deployment checklist.", instance_path=tmp_path)

    result = search_notes("  google calendar  ", max_results=1, instance_path=tmp_path)

    assert result["query"] == "  google calendar  "
    assert len(result["results"]) == 1
    assert result["results"][0]["text"] == "Add Google Calendar support for recurring events."
    assert result["results"][0]["context"].endswith("UTC")
    assert search_notes("groceries", instance_path=tmp_path)["results"][0]["text"] == "Buy GROCERIES: milk and bread."
    assert search_notes("does not exist", instance_path=tmp_path) == {"query": "does not exist", "results": []}
