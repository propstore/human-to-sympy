"""Semantic checks must see authored operations before simplification."""

import pytest
from sympy import Add, Equality, Symbol

from human_to_sympy import generate_sympy_equation, generate_sympy_rhs_with_error, parse_symbolic


def test_cancellation_preserves_dimensional_obligations() -> None:
    parsed = parse_symbolic("x + y - y")
    assert isinstance(parsed, Add)
    assert parsed.free_symbols == {Symbol("x"), Symbol("y")}


@pytest.mark.parametrize("text", ["x = x", "Eq(x, x)"])
def test_equation_does_not_collapse_to_boolean(text: str) -> None:
    parsed = parse_symbolic(text)
    assert isinstance(parsed, Equality)
    assert parsed.lhs == parsed.rhs == Symbol("x")


def test_explicit_binding_overrides_a_builtin_symbol_name() -> None:
    parsed = parse_symbolic("E ^ 2", symbol_names=("E",))
    assert parsed.free_symbols == {Symbol("E")}


def test_output_symbol_supplies_only_a_missing_left_side() -> None:
    parsed = parse_symbolic("m * a", output_symbol="F")
    assert isinstance(parsed, Equality)
    assert parsed.lhs == Symbol("F")
    full = parse_symbolic("F / m = a", output_symbol="other")
    assert isinstance(full, Equality)
    assert Symbol("other") not in full.free_symbols


@pytest.mark.parametrize("text", ["", "a = b = c", "a =", "= b", "[1, 2]"])
def test_invalid_scalar_surface_has_a_parse_failure(text: str) -> None:
    with pytest.raises(ValueError):
        parse_symbolic(text)


@pytest.mark.parametrize("text", [
    "F = F or (m + t)",
    "F = F or unknown",
    "F = F and (m + t)",
    "m = m if r else t",
    "m = Piecewise((m, True), (m+t, False))",
    "m = m + (t if r else 0)",
    "m = [m, m + t][0]",
    "F = (F, m+t)[0]",
    "F = [F, unknown][0]",
    "F = F.__class__(F)",
    "m = (m+t).args[0]",
    "F = (lambda x: 0)(m+t)",
    "F = (lambda x: 0)(unknown)",
    "F = Max(*[F for x in (m+t,)])",
    "F = Max(*{F: m+t})",
    "F = Max(*[F for x in (unknown,)])",
    "F = Max(*(F for x in (unknown,)))",
])
def test_conditional_or_selection_syntax_cannot_erase_authored_obligations(text: str) -> None:
    with pytest.raises(ValueError, match="unsupported authored syntax"):
        parse_symbolic(text)


# A closed set of scalar productions must preserve every authored symbol,
# including inside algebraic identities that normal SymPy parsing simplifies.
@pytest.mark.parametrize("term", ["unknown", "m+t"])
@pytest.mark.parametrize("template", [
    "{} + known", "known - ({})", "0 * ({})", "({}) / known",
    "({}) ** 0", "known ** ({})", "+({})", "-({})", "sin({})",
    "Abs({})", "Min({}, known)", "Max({}, known)", "f({})",
])
def test_supported_scalar_grammar_preserves_operand_symbols(term: str, template: str) -> None:
    parsed = parse_symbolic(template.format(term))
    expected = {Symbol("unknown")} if term == "unknown" else {Symbol("m"), Symbol("t")}
    assert expected <= parsed.free_symbols


@pytest.mark.parametrize("text", [
    "Fa = 1 / (2 * pi * Ta)", "(2*pi*Ta*f)^2", "x**2 + y**2",
    "F = m * a", "Eq(F, F)", "F/m=a", "Rational(1, 2) * m",
    "m = (m^2)^(1/2)", "m = m^(2/2)", "exp(log(x))", "sin(pi*x)",
])
def test_documented_and_existing_scalar_math_stays_supported(text: str) -> None:
    assert parse_symbolic(text) is not None


@pytest.mark.parametrize("unsupported", [
    "Max(*[F for x in (m+t,)])", "Max(*{F: m+t})",
    "Max(*[F for x in (unknown,)])", "Max(*(F for x in (unknown,)))",
    "[m+t]", "(m+t,)", "{m+t}", "{F: unknown}",
    "{F for x in (unknown,)}", "{F: x for x in (unknown,)}",
    "F if unknown else m+t", "F or unknown", "(lambda x: 0)(unknown)",
    "(F, unknown)[0]", "(m+t).args", "f(**{F: unknown})",
    "f(x=unknown)", "(x := unknown)", "f'{unknown}'", "True", "None",
    "F < unknown", "not unknown", "'unknown'", "m // t", "m & t",
])
def test_unsupported_grammar_is_rejected_before_any_symbolic_evaluation(
    unsupported: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_evaluation(*args: object, **kwargs: object) -> None:
        raise AssertionError("unsupported Python syntax reached symbolic evaluation")

    monkeypatch.setattr("human_to_sympy.parse_expr", unexpected_evaluation)
    with pytest.raises(ValueError, match="unsupported authored syntax"):
        parse_symbolic(f"F = {unsupported}")
    rhs = generate_sympy_rhs_with_error(f"F = {unsupported}")
    assert rhs.expression is None
    assert rhs.error is not None
    equation = generate_sympy_equation(f"F = {unsupported}")
    assert equation.lhs is equation.rhs is None
    assert equation.error is not None
