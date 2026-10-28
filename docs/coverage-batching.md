# Coverage batching: scaling write-module unit tests (historical)

> **2026-10-28 — closed by the P1 surface reduction.** This document tracked
> the batching drive that raised unit-test coverage across the pre-reduction
> module surface. The modules, the generated `_info` fleet and the
> test-skeleton generator it describes no longer exist in this collection
> (see [`REMEDIATION.md`](REMEDIATION.md)), so the drive is complete by
> removal rather than by authoring. The full batch log remains in the git
> history of this file.

The methodology that is still worth keeping:

- Drive every module test through the shared harness
  (`tests/unit/plugins/modules/harness.py`) instead of per-file private
  doubles, so a harness fix reaches every module.
- Prefer assertions that encode the module's drift rules over happy-path
  coverage; a test that only proves `changed == true` inflates the number
  without protecting behavior.
- Raise a coverage gate only on a steady-state commit where the measured
  total clears the new floor, never inside a feature batch.

Current testing expectations for the allowlisted modules live in
[`development.md`](development.md), [`testing-e2e.md`](testing-e2e.md) and
the P4 integration contract in [`REMEDIATION.md`](REMEDIATION.md).
