"""Parse human-typed equation strings into canonical SymPy expressions."""

from __future__ import annotations

import ast
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from tokenize import TokenError

from sympy import Eq, Expr, Function, Symbol, SympifyError, evaluate
from sympy.core.relational import Equality
from sympy.parsing.sympy_parser import parse_expr

from human_to_sympy.numeric import (
    NumericEvaluation,
    NumericEvaluationStatus,
    evaluate_numeric,
    parse_cached,
)

_SYMPY_CONSTANTS = {"pi", "E", "I", "oo", "zoo", "nan"}
_IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")
_SYMPY_BUILTINS = {
    "Eq", "exp", "log", "ln", "sqrt", "sin", "cos", "tan", "asin", "acos",
    "atan", "atan2", "sinh", "cosh", "tanh", "Sum", "Product", "Integral",
    "Derivative", "Abs", "Mod", "ceiling", "floor", "sign", "Piecewise",
    "Max", "Min", "re", "im", "conjugate", "Rational", "Float", "Integer",
    "Symbol", "symbols", "Function", "Norm",
    "pi", "E", "I", "oo", "zoo", "nan",
    "true", "false", "True", "False", "None",
}


def _build_local_dict(text: str) -> dict[str, Symbol | Function]:
    function_names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", text)) - _SYMPY_BUILTINS
    names = set(_IDENTIFIER_RE.findall(text)) - _SYMPY_BUILTINS - function_names
    local_dict: dict[str, Symbol | Function] = {name: Symbol(name) for name in names}
    local_dict.update({name: Function(name) for name in function_names})
    return local_dict


def parse_symbolic(
    expression: str, *, symbol_names: Sequence[str] = (), output_symbol: str | None = None,
) -> Expr | Equality:
    """Parse authored scalar math without simplifying away semantic obligations.

    Unlike canonical string generation, this preserves additions, cancellation,
    and equal sides so dimensional checks can inspect the authored operations.
    Explicit bindings also disambiguate names such as ``E`` from constants.
    ``output_symbol`` supplies the left side when the authored text is a RHS.
    """
    text = expression.strip().replace("^", "**")
    if not text:
        raise ValueError("empty expression")
    # Selection can discard unchecked operands even inside evaluate(False).
    # This scalar API does not support conditional or selection semantics.
    for side in text.split("="):
        try:
            syntax = ast.parse(side.strip(), mode="eval")
        except SyntaxError as exc:
            raise ValueError("unsupported authored syntax") from exc
        for node in ast.walk(syntax):
            if isinstance(node, (ast.BoolOp, ast.IfExp, ast.Subscript, ast.Attribute, ast.Lambda)) or (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Piecewise"
            ):
                raise ValueError(f"unsupported authored syntax: {type(node).__name__}")
    local_dict = _build_local_dict(text)
    local_dict.update({name: Symbol(name) for name in symbol_names})
    with evaluate(False):
        if "=" in text:
            if text.count("=") != 1:
                raise ValueError("equation must contain exactly one '='")
            lhs, rhs = (part.strip() for part in text.split("="))
            if not lhs or not rhs:
                raise ValueError("equation must have non-empty left and right sides")
            parsed = Eq(
                parse_expr(lhs, local_dict=local_dict, evaluate=False),
                parse_expr(rhs, local_dict=local_dict, evaluate=False),
                evaluate=False,
            )
        else:
            parsed = parse_expr(text, local_dict=local_dict, evaluate=False)
        if output_symbol is not None and isinstance(parsed, Expr):
            parsed = Eq(Symbol(output_symbol), parsed, evaluate=False)
    if not isinstance(parsed, (Expr, Equality)):
        raise ValueError("expected a scalar expression or equation")
    return parsed


@dataclass(frozen=True)
class SympyGenerationResult:
    expression: str | None
    error: str | None


@dataclass(frozen=True)
class SympyEquationGenerationResult:
    lhs: str | None
    rhs: str | None
    error: str | None


def generate_sympy_rhs_with_error(expression: str | None) -> SympyGenerationResult:
    """Generate a SymPy RHS expression and preserve the failure reason."""
    if not expression or not isinstance(expression, str):
        return SympyGenerationResult(None, "missing expression")

    text = expression.strip()
    if not text:
        return SympyGenerationResult(None, "empty expression")

    text = text.replace("^", "**")

    if "=" in text:
        parts = text.split("=", 1)
        text = parts[1].strip()

    if not text:
        return SympyGenerationResult(None, "expression has no right-hand side")

    try:
        result = parse_expr(text, local_dict=_build_local_dict(text))
        return SympyGenerationResult(str(result), None)
    except (SympifyError, TypeError, ValueError, SyntaxError, TokenError) as exc:
        logging.warning("SymPy parse_expr failed for %r: %s", text, exc)
        return SympyGenerationResult(None, str(exc))


def generate_sympy_rhs(expression: str | None) -> str | None:
    """Generate a SymPy-parseable RHS string from human-readable math."""
    return generate_sympy_rhs_with_error(expression).expression


def generate_sympy_equation(expression: str | None) -> SympyEquationGenerationResult:
    """Generate structured SymPy strings for both sides of an equation."""
    if not expression or not isinstance(expression, str):
        return SympyEquationGenerationResult(None, None, "missing expression")
    text = expression.strip().replace("^", "**")
    if not text:
        return SympyEquationGenerationResult(None, None, "empty expression")
    if text.count("=") != 1:
        return SympyEquationGenerationResult(None, None, "equation must contain exactly one '='")
    lhs_text, rhs_text = (part.strip() for part in text.split("=", 1))
    if not lhs_text or not rhs_text:
        return SympyEquationGenerationResult(None, None, "equation must have non-empty left and right sides")
    try:
        lhs = parse_expr(lhs_text, local_dict=_build_local_dict(lhs_text))
        rhs = parse_expr(rhs_text, local_dict=_build_local_dict(rhs_text))
        return SympyEquationGenerationResult(str(lhs), str(rhs), None)
    except (SympifyError, TypeError, ValueError, SyntaxError, TokenError) as exc:
        logging.warning("SymPy parse_expr failed for equation %r: %s", text, exc)
        return SympyEquationGenerationResult(None, None, str(exc))


def check_symbols(
    expression: str,
    variables: Sequence[Mapping[str, str]],
) -> list[str]:
    """Check that expression free symbols are present in variable bindings."""
    text = expression.strip()
    if not text:
        return []

    text = text.replace("^", "**")
    if "=" in text:
        parts = text.split("=", 1)
        text = parts[1].strip()

    if not text:
        return []

    try:
        expr = parse_expr(text, local_dict=_build_local_dict(text))
    except (SympifyError, SyntaxError, TypeError, ValueError):
        return []

    free = {str(s) for s in expr.free_symbols}
    free -= _SYMPY_CONSTANTS
    declared = {v.get("symbol", "") for v in variables if isinstance(v, Mapping)}
    return [
        f"Symbol '{symbol}' in expression is not in variables list"
        for symbol in sorted(free - declared)
    ]


__all__ = [
    "parse_symbolic",
    "NumericEvaluation",
    "NumericEvaluationStatus",
    "SympyEquationGenerationResult",
    "SympyGenerationResult",
    "check_symbols",
    "evaluate_numeric",
    "generate_sympy_equation",
    "generate_sympy_rhs",
    "generate_sympy_rhs_with_error",
    "parse_cached",
]
