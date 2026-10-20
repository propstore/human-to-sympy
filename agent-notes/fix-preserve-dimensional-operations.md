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
