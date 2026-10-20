# Preserve authored operations for semantic validation

## Goal
Expose the existing parser's nonsimplifying symbolic result for Propstore's
dimension check. Canonical string generation and numeric evaluation stay intact.

## State
Isolated branch fix/preserve-dimensional-operations at
f9d67dd54cb1e5e1c0ef9d67094606eb3497cfd7. No open owner PR overlaps.

## Decisions and why
The current generator returns simplified strings (x + y - y becomes x), which
can erase dimensionally invalid additions before Bridgman sees them. Add one
parser-owner API (~25 lines) using existing symbol recognition and SymPy's
evaluate=False, with optional explicit symbol bindings and both equation/RHS
forms. Return the substrate's symbolic type directly, not another AST model.

## Next step
New API import regression failed before implementation. Eight focused tests now
pass (1.58s): cancellation, equal sides, builtin-name binding, malformed scalar
surfaces. Existing string/numeric APIs are unchanged. Publish draft and read CI.

## Independent review correction
- At 5dd5da9, owner CI passed 35 tests and typing. Independent review ledger
  propstore-human-to-sympy-2.md completed two passes and its review gate passed.
- Functional Eq(x,x) was reduced to True despite the nonsimplifying parse flag;
  reproduced as one failing/eight passing focused cases. SymPy's evaluation
  context must also be disabled while parsing functional constructors.
- Supply an optional output_symbol for a bare RHS in this parser owner, so
  Propstore composes its symbolic result directly without importing untyped
  SymPy constructors. Explicit full equalities retain their authored left side.
- Next: run focused cases, push, verify full CI, then independent delta review.
- Follow-up review reproduced scalar erasure in Python or/and, if expressions,
  Piecewise and tuple/list/attribute selection. Ten new cases failed before
  correction (nine erased operands; __class__ raised an untyped TypeError).
  Reject these unsupported forms through a static syntax walk before SymPy can
  discard any branch. Preserve the existing arithmetic/function path. Include
  missing-symbol erasure and (m+t).args[0] as regressions. Parent requested typed
  unsupported/quarantine rather than implementing new conditional semantics.
- End-to-end follow-up: F = (lambda x: 0)(m+t) was admitted at f05af3d because
  the Python function discarded its authored argument. Consumer red regression
  failed with blocked=False (dimension-lambda-erasure-red-20261020-172729.log).
  Add Lambda to the same pre-evaluation unsupported syntax set; cover both
  invalid-dimensional and missing-symbol arguments. No lambda evaluation or
  lambda semantics is added. Before this final delta, hosted CI39513860531
  passed 48 tests and typing; rerun owner CI at the new final head.
