"""Semantic checks must see authored operations before simplification."""

import pytest
from sympy import Add, Equality, Symbol

from human_to_sympy import parse_symbolic


def test_cancellation_preserves_dimensional_obligations() -> None:
    parsed = parse_symbolic("x + y - y")
    assert isinstance(parsed, Add)
    assert parsed.free_symbols == {Symbol("x"), Symbol("y")}


def test_equation_does_not_collapse_to_boolean() -> None:
    parsed = parse_symbolic("x = x")
    assert isinstance(parsed, Equality)
    assert parsed.lhs == parsed.rhs == Symbol("x")


def test_explicit_binding_overrides_a_builtin_symbol_name() -> None:
    parsed = parse_symbolic("E ^ 2", symbol_names=("E",))
    assert parsed.free_symbols == {Symbol("E")}


@pytest.mark.parametrize("text", ["", "a = b = c", "a =", "= b", "[1, 2]"])
def test_invalid_scalar_surface_has_a_parse_failure(text: str) -> None:
    with pytest.raises(ValueError):
        parse_symbolic(text)
