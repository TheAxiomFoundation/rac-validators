# Scope of rulespec-validators

This document clarifies what `rulespec-validators` is responsible for and what
belongs elsewhere in the Axiom Foundation toolchain. It exists because an
internal review flagged that parts of the `harness/quality/` tree overlap
with work that `rulespec-compile` already does (or could do) during compilation.

## What rulespec-validators IS

`rulespec-validators` is an **oracle-consensus** framework for encoded statutes.
Given a RuleSpec encoding of a tax or benefit rule and a set of test cases with
expected values, it:

1. **Runs the encoding against multiple independent oracle systems**
   (PolicyEngine, TAXSIM, PSL / Tax-Calculator, Yale Tax-Simulator).
2. **Aggregates the results** into a single consensus value, confidence
   score, and a reward signal in the range `[-1.0, +1.0]` suitable for
   training AI encoders.
3. **Flags upstream bugs** when the Claude encoder is highly confident,
   the citation is clear, and one or more oracle systems disagree with
   the expected value.

In short: `rulespec-validators` answers "*does this encoding behave the same
way as every established calculator of record, and if not, which one is
wrong?*" It operates at **runtime**, on **calculated outputs**.

## What rulespec-validators is NOT

`rulespec-validators` is **not** a compile-time or static-analysis tool. It
does not (and should not) own:

- Grammar/syntax validation of `.yaml` files — that is `rulespec-syntax`.
- Type checking, import resolution, schema checks, or any other
  compile-time linting of an encoding — that is `rulespec-compile`.
- The RuleSpec DSL semantics themselves — that is `rulespec`.

If a check can be performed by reading the source of a `.yaml` file
without running any oracle, it probably belongs in `rulespec-compile`.

## Known overlap

The following modules currently duplicate logic that belongs in (or is
already in) `rulespec-compile`:

| Module | Overlap with rulespec-compile |
|---|---|
| `harness/quality/imports.py` | Validates that `path#variable` imports resolve. This is a static-source check. |
| `harness/quality/schema.py` | Checks YAML/schema shape of `.yaml` files. Compile-time concern. |
| `harness/quality/grounding.py` | Citation / source-grounding checks. Partially static; runtime grounding stays here. |

Each of these modules has been tagged with a module-level comment:

```python
# NOTE: This may move to rulespec-compile. See docs/scope.md.
```

**Migration is under consideration but is not scheduled.** The overlap is
tolerated for now because:

- The harness needs *some* quality gate before running oracles — a
  malformed `.yaml` file should fail fast rather than cause opaque
  oracle errors.
- Moving checks requires a coordinated release of `rulespec-compile` and
  a new integration surface here. That work is tracked separately.

If you add new quality checks, prefer extending `rulespec-compile` and
importing from it rather than adding logic under `harness/quality/`.

## Decision rule

When deciding where a new check belongs:

- **Reads only the `.yaml` source?** → `rulespec-compile`.
- **Runs an oracle or compares numerical outputs?** → `rulespec-validators`.
- **Concerns the DSL grammar itself?** → `rulespec-syntax` or `rulespec`.
