# Coverage batching: scaling write-module unit tests (roadmap #57)

How to raise the CI coverage gate (55%) back towards 70% without writing
~200 module test files one by one at the current per-batch pace.

## Current state (measured 2026-09-02)

- Gate: `--cov-fail-under=55`, baseline total ~60.9% after batches 1-11.
- 313 write modules, 222 of them have **no** unit test file.
- Target 70% needs roughly +4,000 covered statements. The untested write
  modules are the entire gap (module_utils at 92%, `_info` at ~86% are
  already near their ceiling).

## The untested 222 are not one population

Structural scan (top-level `def`s) splits them into three groups:

| Group | Count | Shape | Example |
|---|---|---|---|
| A: waiter CRUD | 20 | `_load` + `find*` + `wait*` + `run_module` + `main` | `vdb_instance`, `thpc_cluster` |
| B: plain CRUD | 155 | `_load` + `find*` + `run_module` + `main`, no waiter | `alb_*`, `api_gateway_*` |
| C: run-only / other | 47 | `run_module` present but no `find*`/no `_load` | thin wrappers, odd shapes |

Groups A+B (175 modules) share the exact helper skeleton the batches 1-11
harness already targets: lazy `_load` (returns models + client module),
request builders, a `find*` identify helper, `run_module` switch over
state, `main`. The per-test boilerplate is measurable: batch 11's
`test_ccn_attachment.py` is 382 lines, of which **172 (45%)** are imports,
constants, fake client/store fixtures and setup — identical shape across
all of A+B.

## Proposal: two levers

### 1. A test-skeleton generator (biggest win, low risk)

Extend `scripts/generate_info_modules.py` (or a sibling script) with a
`--module-test <module>` mode that statically reads one write module and
emits a complete, runnable harness test file:

- imports + `module_args`/`run`/`AnsibleFailJson`/`FakeModels`/
  `FakeResource` from `tests/unit/plugins/modules/harness.py`;
- a fake client whose write-mutation methods update an in-memory store
  (mirroring the `ATTACHMENT`-store pattern from batches 8-11), so waiter
  polls converge on the first attempt;
- one test stub per state branch found in `run_module`
  (present/absent/check-mode) and one per helper (`find*`, `_wait`,
  each `build_*_request`), each marked with the exact module lines it
  should exercise.

The generated file is a **starting point**, not a pass: assertions are the
human part (they encode each module's drift rules). What the generator
kills is the 45% boilerplate + the "which functions exist" discovery —
the part that is identical across 175 modules.

Expected effect: per-module authoring time drops from ~1-2 h (current
batches) to ~20-40 min of assertion writing. At 3-5 modules per batch the
+4,000-statement gap closes in ~10-15 batches instead of ~180.

### 2. Batch triage order

Do not go alphabetically. Order by expected statement gain per authoring
hour:

1. **Group B plain CRUD first** — no waiter means no clock-patching, no
   poll-convergence store; smallest test surface per module.
2. Inside B, prefer the largest files first (`alb_*` and `api_gateway_*`
   families are 300-580 lines) — statement gain scales with file size.
3. Group A (waiters) only after B is cleared, reusing the patched-clock
   timeout pattern already shipped in batches 8-11.
4. Group C last — thin wrappers give the least coverage per hour; several
   may already be partially covered via contract tests.

### Guardrails (keep the gate green)

- Each batch must leave `--cov-fail-under=55` green (current margin
  ~+6 pp).
- Run the full module unit suite + `ansible-test sanity` before each
  commit, exactly as batches 1-11 did.
- Do not raise the gate in the same commit as a batch; raise it only on a
  steady-state commit where the measured total clears the new floor.

## Rejected alternatives

- **Wholesale generation with no human assertions** (auto-assert
  `changed == True` everywhere): fails because drift/no-change paths are
  exactly what idempotent modules must prove; a test that only exercises
  the happy path would inflate coverage while hiding regressions. Worth
  < 60% real protection for the same authoring cost.
- **Raising `--cov-fail-under` to 70 now and treating CI red as a
  "coverage debt" tracker**: was the born-red state of 2026-08-31; red
  CI stops being a signal. Rejected.
- **Excluding write modules from the gate** (`.coveragerc` omit): would
  make the metric pass but un-ship the entire regression story; the gate
  exists because the generated `_info` batch made write modules the only
  untested surface left.

## Decision needed

Adopt lever 1 (write the generator) — it is the only option that turns
~180 one-off authoring sessions into ~15 batch sessions. Scope is a
~200-line script plus one reference generated test to review.
