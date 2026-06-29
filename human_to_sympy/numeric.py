"""Typed numeric evaluation of SymPy expressions under symbol bindings.

This is the package's owned boundary for *numeric* SymPy use (the parsing/string
side lives in the package root). Callers pass an expression string and a
``symbol -> value`` binding map and receive a typed :class:`NumericEvaluation`
that distinguishes a value from each way evaluation can decline to produce one,
so no caller collapses "missing input", "no solution", "non-numeric", and
"unparseable" into a single overloaded ``None``.

Two expression shapes are handled in one call:

* a bare expression (``a + b``) — substitute the bindings and evaluate;
* an equality (``Eq(y, expr)``) — substitute the bindings and solve for
  ``output_symbol``.

``output_symbol`` also names the result symbol that must NOT be treated as an
input: if it appears in ``bindings`` (a self-referencing relationship) its bound
value is excluded before substitution.

SymPy is a hard dependency of this package; there is no "sympy unavailable"
state. Expected SymPy failures (parse errors, non-numeric results) become typed
statuses; an unexpected error (e.g. a patched parser raising ``RuntimeError``)
propagates so callers never silently lose a real fault.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class NumericEvaluationStatus(StrEnum):
    """How a numeric evaluation resolved."""

    VALUE = "value"
    INVALID_EXPRESSION = "invalid_expression"
    MISSING_INPUT = "missing_input"
    NO_SOLUTION = "no_solution"
    NON_NUMERIC = "non_numeric"


@dataclass(frozen=True)
class NumericEvaluation:
    """The typed outcome of :func:`evaluate_numeric`."""

    status: NumericEvaluationStatus
    value: float | None = None
    detail: str | None = None

    @classmethod
    def from_value(cls, value: float) -> NumericEvaluation:
        return cls(NumericEvaluationStatus.VALUE, value=value)


@functools.lru_cache(maxsize=128)
def parse_cached(
    expression: str, symbol_names: tuple[str, ...]
) -> tuple[Any, dict[str, Any]]:
    """Parse ``expression`` with the named symbols, memoized by (text, names).

    The SymPy parser is imported lazily inside the call so that tests patching
    ``sympy.parsing.sympy_parser.parse_expr`` take effect; clear the memo with
    ``parse_cached.cache_clear()`` when patching.
    """

    from sympy import Symbol
    from sympy.parsing.sympy_parser import parse_expr

    symbols = {name: Symbol(name) for name in symbol_names}
    return parse_expr(expression, local_dict=symbols), symbols


def evaluate_numeric(
    expression: str,
    bindings: Mapping[str, float],
    output_symbol: str,
) -> NumericEvaluation:
    """Evaluate ``expression`` numerically under ``bindings``.

    For a bare expression the bindings are substituted directly; for an
    ``Eq(...)`` the bindings are substituted and the equation is solved for
    ``output_symbol``. ``output_symbol`` is excluded from the substituted inputs
    so a self-referencing binding does not pin the value being solved for.
    """

    from sympy import Equality, Symbol, solve

    all_names = set(bindings) | {output_symbol}
    try:
        parsed_expr, symbols = parse_cached(expression, tuple(sorted(all_names)))
    except (TypeError, ValueError, SyntaxError, AttributeError) as exc:
        return NumericEvaluation(
            NumericEvaluationStatus.INVALID_EXPRESSION, detail=str(exc)
        )

    effective = {
        name: value for name, value in bindings.items() if name != output_symbol
    }

    def _numeric(value: Any) -> NumericEvaluation:
        try:
            numeric = float(value)
        except (TypeError, ValueError, ZeroDivisionError, AttributeError) as exc:
            return NumericEvaluation(
                NumericEvaluationStatus.NON_NUMERIC, detail=str(exc)
            )
        if not math.isfinite(numeric):
            return NumericEvaluation(
                NumericEvaluationStatus.NON_NUMERIC, detail=repr(value)
            )
        return NumericEvaluation.from_value(numeric)

    try:
        if isinstance(parsed_expr, Equality):
            output_sym = symbols.get(output_symbol)
            if output_sym is None:
                output_sym = Symbol(output_symbol)
            subs_pairs = [
                (symbols[name], value)
                for name, value in effective.items()
                if name in symbols
            ]
            substituted = parsed_expr.subs(subs_pairs)
            missing = substituted.free_symbols - {output_sym}
            if missing:
                return NumericEvaluation(
                    NumericEvaluationStatus.MISSING_INPUT,
                    detail=", ".join(sorted(str(symbol) for symbol in missing)),
                )
            solutions = solve(substituted, output_sym)
            if solutions:
                return _numeric(solutions[0])
            return NumericEvaluation(NumericEvaluationStatus.NO_SOLUTION)

        subs_pairs = [
            (symbols[name], value)
            for name, value in effective.items()
            if name in symbols
        ]
        result = parsed_expr.subs(subs_pairs)
        if result.free_symbols:
            return NumericEvaluation(
                NumericEvaluationStatus.MISSING_INPUT,
                detail=", ".join(sorted(str(symbol) for symbol in result.free_symbols)),
            )
        return _numeric(result)
    except (TypeError, ValueError, ZeroDivisionError, AttributeError) as exc:
        return NumericEvaluation(
            NumericEvaluationStatus.INVALID_EXPRESSION, detail=str(exc)
        )
