# Inclusion remediation record

What changed after the review of
[ansible-inclusion#89](https://github.com/ansible-collections/ansible-inclusion/discussions/89),
with the command to check every claim. Review date 2026-09-22; this record
covers the remediation through 2026-09-24.

## What the review found

The published checklist entry left four items unchecked, and the reviewer
raised a separate concern on the forum:

> It's a low quality AI generated content: 1000+ modules with unreadable
> documentation, 500+ forbidden codes in ignore.txt's. Do we really want to
> bloat the package and docs.ansible.com with collections developed in such a
> way?

Three of those are accurate and are fixed below. Two numbers in the review are
loose and are corrected here rather than quietly accepted: the collection has
1,027 modules, not "1000+" against a 524-module self-check, and the 519 lines
in an ignore file are its total size, of which 313 named a code that must not
be ignored.

## What was actually wrong

The self-check posted to #89 was wrong in four places, and those four are what
turned a code-quality review into a trust problem. Correcting them is the
first item of this record:

| The self-check said | Measured |
| --- | --- |
| "No `test/sanity/ignore*.txt` — no errors ignored" | The files exist at `tests/sanity/`, 519 entries each, byte-identical across all four. `test/sanity/` in the checklist wording is ansible-core's own legacy layout; ansible-test reads `tests/sanity/`. |
| "zero ... markers across all 524 modules" | 1,027 modules: 457 write + 570 `_info`. |
| "README declares ansible-core 2.19+ / Python 3.11+" | The README said 2.16 / Python 3.10 while `meta/runtime.yml` says `>=2.19.0` and CI tests 3.11–3.13. |
| "`ansible-test sanity` passes" | It had not run on `main` since 2026-09-23: the "Docs figures" step failed, and because it sat *before* the sanity step in the same job, sanity and units were skipped on every push after it. |

That last one hid the actual defect: **1,625 `validate-modules` errors** on the
commit this work was rebased onto.

The merge `eecbc03e` ("Merge remote main with local capability work") kept the
three-fragment `extends_documentation_fragment` block from one parent and
dropped the `retry` / `user_agent` / `waiter` fragments the other parent had
added, so 509 modules documented four options they accept nowhere.
`scripts/sync_doc_fragments.py` could not see it — it added an option fragment
only when it found an inline copy to strip, so a module with neither the
inline text nor the fragment was reported as "nothing to do".

## Changes

Each claim below is checkable with the command in the same row.

| Claim | Verify with |
| --- | --- |
| `ansible-test sanity` is green across all 24 tests on ansible-core 2.19 / 2.20 / 2.21 | `ansible-test sanity` |
| Zero `validate-modules` errors (was 1,625) | `ansible-test sanity --test validate-modules` |
| The ignore files carry no must-not-ignore code and every entry is justified | `python scripts/check_sanity_ignore.py` |
| Ignore entries are down to 36 per file | `python scripts/check_sanity_ignore.py --print` |
| No module documents options as single-line flow mappings (was 372 on this base) | `python scripts/normalize_module_docs.py --check` |
| All 1,027 modules document check mode and idempotency | `python scripts/add_module_attributes.py --check` |
| Every module declares GPL-3.0-or-later in its header (181 were missing) | `python scripts/fix_module_headers.py --check` |
| Generated and hand-written modules cannot drift on documentation style | `python scripts/generate_info_modules.py --check` |
| The fragment set matches each module's `argument_spec` | `python scripts/sync_doc_fragments.py --check` |
| Every shipped example runs as written | `python scripts/check_module_examples.py --check` |
| Every module links to its read-only counterpart | `python scripts/add_module_seealso.py --check` |
| Every role declares the core floor the collection requires | `python scripts/check_quality_gates.py` |

### A guard for the examples that ship inside modules, and what it found

Nothing validated the `EXAMPLES` block *inside* a module. `validate-modules`
proves the string exists and parses as YAML; `scripts/check_examples.py` reads
the playbooks under `docs/examples/` and `playbooks/` but not the examples that
ship in the 1,027 modules; and the integration targets, which would run one,
need an account. The example is the first thing a user copies, and it was the
one part of a module no check read.

`scripts/check_module_examples.py` closes that statically. It resolves every
module an example calls, checks each option against the module's own
`DOCUMENTATION` and doc fragments, and checks that options the module marks
`required` are passed. Its first run found three defects that had shipped:

- `tse_governance_alias_info` called `tse_governance_aliase_info`, a module
  that does not exist, so the example failed with "couldn't resolve
  module/action" before reaching Tencent Cloud.
- `lcic_answer_info` omitted `question_id`, which its argument spec marks
  required, so the example failed with "missing required arguments".
- `cdb_audit_rule` shipped a delete example without `rule_filters` while the
  argument spec marked that option unconditionally required — the
  documentation said "required when `state=present`", the code said always, and
  the code won, which made deleting an audit rule impossible. `required_if`
  already expressed the intent; the unconditional requirement is gone. The
  unit tests passed throughout because they passed the filters on the delete
  path too, which is how a test holds a bug in place rather than catching it.

The first two are documentation defects. The third is a functional one, and it
is the reason the guard checks `required` and not only option names.

### The ignore files are a ratchet now, not a budget

`scripts/check_sanity_ignore.py` used to enforce `BASELINE_TOTAL = 2600`, a
budget for 2,076 committed entries with headroom above it, and
`.github/workflows/devel.yml` documented copying `ignore-2.21.txt` to
`ignore-2.22.txt` when a new ansible-core minor arrives. That is the opposite
of the requirement, which is that the must-not-ignore codes are fixed and
removed before approval and that every entry carries a justification.

The guard now fails on any must-not-ignore code, requires a `#` justification
per entry, and allows the per-code count only to decrease.

### `timeout` moved into its own fragment

`dlc_notebook_session`, `tat_command`, `tat_invocation` and
`tse_gateway_service` define their own `timeout` for a product API field, which
shadowed the shared request-timeout option and dropped its default —
`validate-modules` reported "spec defines None, documentation defines 60".
Documenting it inline cannot win against a fragment default, and giving it the
fragment default would change what the module sends. `timeout` therefore lives
in `plugins/doc_fragments/timeout.py`: the 1,022 modules that accept the shared
option reference it, the four that shadow it document their own. No behaviour
change and no breaking rename.

### The bucket readers moved into `module_utils`

Nine `cos_bucket_*_info` modules imported their write-module counterpart, which
the `import` sanity test rejects because a module must not import another
module. The readers now live in `plugins/module_utils/cos.py` and both sides
import them from there.

### Failures that were already on `main`

Four checks were red on `main` before this work started, each masked because it
sits *before* the sanity step in the same CI job, so nothing downstream ever
ran.  They are fixed here as well, since a green pipeline is the point:

- `scripts/sync_registry.py --check` failed because the README's two count
  slots ("Browse all N resource modules" and "Browse all N read-only
  `_info` modules") had lost their numbers, so the registry could not be
  substituted into them.
- Two modules added after that (`tcr_internal_endpoint` and
  `tcr_internal_endpoint_info`) were missing from the README index, which
  `check_roadmap_status.py` rejects because P1-09 is marked done.
- `docs/capability-map.html`, `docs/roadmap.md` and `docs/gap-closure.md`
  still stated 1,025 modules; P0-12 requires the current count.
- `generate_cam_actions.py --check` reported a stale manifest.

One contract test was also red: `test_tke_cluster_deletion_protection` used a
`DescribeClusters` fixture without a `ClusterId`, but the module now fails
closed unless exactly one returned cluster matches the id it asked for, so
`describe_state` called `fail_json` on a double that has no `fail_json` and
raised `AttributeError`. The fixture carries the id now.

### The core subset, and what it still does not reach

1,027 modules across 220 product prefixes is not a claim anyone can review.
`tests/quality/core-subset.yml` names the 35 products this collection asks to
be judged on — 317 modules — and `scripts/check_quality_gates.py` holds two
ratchets over it and over everything else:

- **no option description may merely repeat the option name.** This is
  deliberately not a length rule: a length threshold flags thousands of good
  one-line descriptions ("Whether the listener should exist.") while missing
  the actual defect, and a gate that cries wolf gets disabled — which is how
  the sanity ignore files reached 519 entries. 91 remain, all outside the core
  subset; the 12 inside it are written.
- **a core write module must have an integration target that runs.** This is
  the honest number and it is uncomfortable: the workflow dispatches 21
  targets covering **24 of the 166 write modules in the core subset**, and 20
  core products — cvm, tke, cbs, redis, mongodb, postgresql, mariadb,
  sqlserver, tdmysql, cynosdb, alb, as, dnspod, eks, lighthouse and others —
  have no covered write module at all. The dispatch list is ordered by cost
  tier, so the modules users need most were exactly the ones left out.

**That gap, not the documentation, is the largest remaining distance between
this collection and the standard it claims.** Closing it needs integration
targets written against a real account, and the ratchet makes the distance
visible in every CI run until they are.

## What this record does not claim

- **1,509 option descriptions (26%) are still under 25 characters**
  ("ALB ID.", "Desired state."). They are readable now, not informative.
  1,399 of them are in write modules, spread over 443 modules at about three
  each, and the repository has a machine-readable option-to-SDK-field map for
  only 36 of them. Filling these in needs per-option product knowledge;
  generating them mechanically is the thing this review objected to, so it is
  left as authoring work rather than automated.
- **Three modules declare `idempotency: partial`**: `cvm_instance`
  (`state=rebooted`), `cdb_instance` and `tdcpg_instance_state`
  (`state=restarted`) act on every run by definition. The attribute names the
  state so the claim can be checked.
- **`scripts/check_doc_figures.py` and docs/panorama.html are coupled through
  Chinese anchor strings.** The dashboard and the guard that reads it are both
  internal working documents; the guard works, but the coupling is fragile.
- **No integration run is claimed here.** The integration targets need a real
  Tencent Cloud account.
