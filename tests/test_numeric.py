from __future__ import annotations

from unittest.mock import patch

import pytest

from human_to_sympy import (
    NumericEvaluation,
    NumericEvaluationStatus,
    evaluate_numeric,
    parse_cached,
)


def test_bare_expression_evaluates_to_value() -> None:
    result = evaluate_numeric("a + b", {"a": 1.0, "b": 2.0}, "out")
    assert result.status is NumericEvaluationStatus.VALUE
    assert result.value == 3.0


def test_equality_is_solved_for_output_symbol() -> None:
    result = evaluate_numeric("Eq(out, a * b)", {"a": 3.0, "b": 4.0}, "out")
    assert result.status is NumericEvaluationStatus.VALUE
    assert result.value == 12.0


def test_self_referencing_binding_is_excluded_before_solving() -> None:
    # ``out`` is bound but must be ignored: the equation is solved for it.
    result = evaluate_numeric("Eq(out, a * 2)", {"a": 5.0, "out": 999.0}, "out")
    assert result.status is NumericEvaluationStatus.VALUE
    assert result.value == 10.0


def test_caret_is_not_special_here_but_power_evaluates() -> None:
    result = evaluate_numeric("a ** 2", {"a": 4.0}, "out")
    assert result.status is NumericEvaluationStatus.VALUE
    assert result.value == 16.0


def test_unbound_symbol_reports_missing_input() -> None:
    result = evaluate_numeric("a + b", {"a": 1.0}, "out")
    assert result.status is NumericEvaluationStatus.MISSING_INPUT
    assert result.detail == "b"


def test_equality_with_unbound_symbol_reports_missing_input() -> None:
    result = evaluate_numeric("Eq(out, a + b)", {"a": 1.0}, "out")
    assert result.status is NumericEvaluationStatus.MISSING_INPUT
    assert result.detail == "b"


def test_unsatisfiable_equation_reports_no_solution() -> None:
    # ``Eq(a, b)`` stays an equality at parse time (a, b distinct symbols) and
    # only collapses to a contradiction once 1 != 2 is substituted, so the solve
    # for ``out`` yields no solution rather than a parse-time boolean.
    result = evaluate_numeric("Eq(a, b)", {"a": 1.0, "b": 2.0}, "out")
    assert result.status is NumericEvaluationStatus.NO_SOLUTION


def test_division_by_zero_is_non_numeric() -> None:
    result = evaluate_numeric("a / b", {"a": 1.0, "b": 0.0}, "out")
    assert result.status is NumericEvaluationStatus.NON_NUMERIC


def test_unparseable_expression_is_invalid() -> None:
    result = evaluate_numeric("@@@ not math", {}, "out")
    assert result.status is NumericEvaluationStatus.INVALID_EXPRESSION


def test_from_value_constructs_value_status() -> None:
    evaluation = NumericEvaluation.from_value(2.5)
    assert evaluation.status is NumericEvaluationStatus.VALUE
    assert evaluation.value == 2.5


def test_unexpected_parser_error_propagates() -> None:
    parse_cached.cache_clear()
    try:
        with patch(
            "sympy.parsing.sympy_parser.parse_expr",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                evaluate_numeric("a + b", {"a": 1.0, "b": 2.0}, "out")
    finally:
        parse_cached.cache_clear()
