# Module tiers

Every module in `plugins/modules/` belongs to exactly one tier. The
assignment is enforced by `scripts/check_module_tiers.py` in CI, so a new
module cannot land without a deliberate tier decision.

| Tier | Meaning | How to recognize | Quality bar |
| --- | --- | --- | --- |
| **core** | Hand-written modules: idempotent write modules and hand-written `*_info` modules | Listed in `CORE_MODULES` in `scripts/check_module_tiers.py` | Idempotent, check mode, diff output, contract tests, unit tests, full documentation |

The pre-reduction **generated** tier (`*_info` modules rendered by
`scripts/generate_info_modules.py`) no longer exists: the P1 surface
reduction removed every generated module, and
[`REMEDIATION.md`](REMEDIATION.md) forbids reintroducing generation.

## Core modules

The write modules are the collection's quality anchor. Each one:

- is idempotent (a second run reports `changed=false`),
- supports check mode (`supports_check_mode=True`, no API write in check mode),
- returns `tc_api_calls` on success and failure (audit trail for the
  `tencentcloud_resource_actions` callback),
- exposes API request IDs on failure,
- is covered by `tests/unit/plugins/modules/` unit tests **and**
  `tests/contract/test_sdk_contracts.py` contract tests against the real SDK.

The hand-written `*_info` modules (e.g. `vpc_info`, `cam_user_info`) are core
as well: they are the read halves of their write-module pairs.

## Adding a module

1. Amend [`core-allowlist.yml`](core-allowlist.yml) under the ratchet in
   [`REMEDIATION.md`](REMEDIATION.md) — without that, the change is rejected.
2. Implement per the core quality bar, add unit + contract coverage, add the
   name to `CORE_MODULES`.
3. Run `python scripts/check_module_tiers.py --check` and
   `python scripts/sync_registry.py` (updates
   `meta/runtime.yml` action groups).
