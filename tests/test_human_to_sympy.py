from __future__ import annotations

from unittest.mock import patch

import pytest

from human_to_sympy import (
    check_symbols,
    generate_sympy_equation,
    generate_sympy_rhs,
    generate_sympy_rhs_with_error,
)


def test_simple_equation_rhs_is_valid_sympy() -> None:
    result = generate_sympy_rhs("Fa = 1 / (2 * pi * Ta)")

    assert result is not None
    import sympy
    assert sympy.sympify(result) is not None


def test_caret_to_power() -> None:
    result = generate_sympy_rhs("(2*pi*Ta*f)^2")

    assert result is not None
    import sympy
    assert sympy.sympify(result) is not None
    assert "^" not in result


def test_unparseable_returns_none() -> None:
    assert generate_sympy_rhs("unparseable garbage !@#") is None


def test_rd_equation_has_expected_symbols() -> None:
    result = generate_sympy_rhs("Rd = (Uo / Ee) * (F0 / 110) * 1000")

    assert result is not None
    import sympy
    expr = sympy.sympify(result)
    symbol_names = {str(s) for s in expr.free_symbols}
    assert "Uo" in symbol_names
    assert "Ee" in symbol_names
    assert "F0" in symbol_names


def test_simple_subtraction() -> None:
    result = generate_sympy_rhs("OQ = 1 - CQ")

    assert result is not None
    import sympy
    expr = sympy.sympify(result)
    symbol_names = {str(s) for s in expr.free_symbols}
    assert "CQ" in symbol_names


def test_empty_expression_returns_none() -> None:
    assert generate_sympy_rhs("") is None
    assert generate_sympy_rhs("   ") is None


def test_expression_without_equals() -> None:
    result = generate_sympy_rhs("x**2 + y**2")

    assert result is not None
    import sympy
    expr = sympy.sympify(result)
    symbol_names = {str(s) for s in expr.free_symbols}
    assert "x" in symbol_names
    assert "y" in symbol_names


def test_none_input_returns_none() -> None:
    assert generate_sympy_rhs(None) is None


def test_unexpected_parse_runtime_error_propagates() -> None:
    with patch(
        "human_to_sympy.parse_expr",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            generate_sympy_rhs_with_error("x + 1")


def test_matching_symbols_no_warnings() -> None:
    variables = [
        {"symbol": "Uo", "concept": "c1"},
        {"symbol": "Ee", "concept": "c2"},
        {"symbol": "F0", "concept": "c3"},
    ]
    warnings = check_symbols("Rd = (Uo / Ee) * (F0 / 110) * 1000", variables)
    assert warnings == []


def test_extra_symbol_produces_warning() -> None:
    variables = [
        {"symbol": "Uo", "concept": "c1"},
        {"symbol": "Ee", "concept": "c2"},
    ]
    warnings = check_symbols("Rd = (Uo / Ee) * (F0 / 110) * 1000", variables)
    assert len(warnings) >= 1
    assert any("F0" in warning for warning in warnings)


def test_unparseable_expression_returns_empty() -> None:
    assert check_symbols("garbage !@#", []) == []


def test_empty_variables_list() -> None:
    warnings = check_symbols("x + y", [])
    assert len(warnings) >= 2


def test_constants_not_warned() -> None:
    variables = [{"symbol": "Ta", "concept": "c1"}]
    warnings = check_symbols("1 / (2 * pi * Ta)", variables)
    assert not any("pi" in warning for warning in warnings)


def test_rhs_generator_name_declares_rhs_only_contract() -> None:
    result = generate_sympy_rhs_with_error("y = f(x)")

    assert result.expression == "f(x)"
    assert result.error is None
    assert generate_sympy_rhs("y = f(x)") == "f(x)"


def test_equation_generator_preserves_distinct_left_hand_sides() -> None:
    y_equation = generate_sympy_equation("y = f(x)")
    z_equation = generate_sympy_equation("z = f(x)")

    assert y_equation.error is None
    assert z_equation.error is None
    assert y_equation.lhs == "y"
    assert z_equation.lhs == "z"
    assert y_equation != z_equation
