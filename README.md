# human-to-sympy

Parse human-typed equation strings into canonical SymPy expression strings.

`human-to-sympy` accepts the kind of math people actually type — `^` for power,
familiar function names, bare identifiers — and returns the corresponding SymPy
expression as a normalized string. It does not perform equivalence comparison;
for that, use [`eq-equiv`](https://github.com/ctoth/eq-equiv).

## What it does

- Replaces `^` with `**`.
- Splits on `=` when present and returns the right-hand side (for
  `generate_sympy_rhs*`) or both sides (for `generate_sympy_equation`).
- Distinguishes function-call sites from bare identifiers and binds them to
  `sympy.Function` and `sympy.Symbol` respectively, while leaving SymPy
  builtins (`pi`, `E`, `log`, `sin`, ...) alone.
- Returns a typed result object preserving the failure reason on parse error.

## API

```python
from human_to_sympy import (
    SympyEquationGenerationResult,
    SympyGenerationResult,
    check_symbols,
    generate_sympy_equation,
    generate_sympy_rhs,
    generate_sympy_rhs_with_error,
)
```

- `generate_sympy_rhs(text) -> str | None` — convenience accessor for the RHS
  string.
- `generate_sympy_rhs_with_error(text) -> SympyGenerationResult` — same, but
  preserves the parse error.
- `generate_sympy_equation(text) -> SympyEquationGenerationResult` — returns
  both sides of an `lhs = rhs` equation.
- `check_symbols(text, variables) -> list[str]` — warns when expression free
  symbols are not declared in the supplied variable list.

## Example

```python
from human_to_sympy import generate_sympy_rhs

assert generate_sympy_rhs("Fa = 1 / (2 * pi * Ta)") == "1/(2*pi*Ta)"
assert generate_sympy_rhs("(2*pi*Ta*f)^2") == "(2*pi*Ta*f)**2"
```
