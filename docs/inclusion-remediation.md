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
| Every core module's `state` says what its choices do | `python scripts/enrich_state_docs.py --check` |
| Every core id/name pair says which one to give | `python scripts/enrich_identity_docs.py --check` |
| Every module that can delete shows how | `python scripts/add_delete_examples.py --check` |
| Every module documents the keys it returns | `python scripts/check_return_docs.py --check` |
| The examples, every integration target and every role task resolve | `python scripts/check_examples.py --check` |
| Every shared helper is covered by its own tests | `python scripts/check_shared_coverage.py --coverage-xml coverage.xml` |
| Every captured `RETURN` sample still matches the payload its module's tests produce | `python scripts/add_return_samples.py --check` |
| Every option that is a secret by name carries `no_log`, and no message interpolates one | `python scripts/check_secret_handling.py --check` |
| Every option a plugin documents is an option it reads | `python scripts/check_plugin_options.py --check` |
| Every option a module declares is an option it reads | `python scripts/check_module_options.py --check` |
| The SDK release the artifacts were generated from is one users may install | `python scripts/check_sdk_drift.py --check` |
| Every SDK reference resolves at the declared SDK floor | `python scripts/check_sdk_floor.py --check` |
| The debt censuses are frozen and may only shrink | `python scripts/check_quality_gates.py` |

### The targets are checked, not just written

`check_examples.py` validated the example playbooks: module names resolve,
options are declared, variables are defined. The 34 integration targets had
none of that. They needed it more — a target runs only in the credentialed
weekly job, and eight of them are gated and never dispatched, so a renamed
option costs a real run against a real account to discover.

The same rules now apply to a target, which is a list of tasks rather than a
play. Two rules had to be right first, and both were the reason the first run
reported 17 of 34 targets as broken:

* a task's own `vars:` are in scope. The targets build the payload a later task
  compares against in a `vars:` block on the task that creates it, and the
  checker did not count them.
* `x is changed` and `x is not failed` read a Jinja *test*. The checker took
  `failed` for a variable.

Fixing the first also removed a latent false positive in the playbook checker,
which had the same blind spot. All 34 targets pass, and the three failures the
check is meant to catch — a module that does not exist, an option that is not
declared, a variable nobody defines — were each verified by breaking a target
and watching it fail.

### The 68 roles are checked too

The roles were the last place a module call went unchecked. The example
playbooks are validated, the integration targets are validated, and a role's
own task files were not — and no test executes a role either, because that
needs an account. So a renamed option or a module that no longer exists in a
role would have been found by a user's first playbook run rather than by CI,
in the part of the collection most people actually copy.

`check_examples.py` now walks `roles/*/tasks/**/*.yml` with the same rules,
against the scope a role really has: its `defaults/main.yml` inputs, its
`vars/main.yml`, everything it `set_fact`s or `register`s, and everything its
own files define for each other — 128 task files, checked in the same run as
the playbooks and the targets.

Two rules had to be fixed to make that scope right, and both were false
positives in the checker rather than defects in the roles:

* a role's task files include each other, so a `loop_var` declared in
  `main.yml` (`loop_var: _tc_rabbitmq_vhost`) is the variable the included
  file reads. Reading each file in isolation reported every such handoff as an
  undefined variable;
* `lookup('…resource_id', name, resource_type='vpc', region=…)` reads exactly
  two variables. The checker counted the function name and the keyword names
  as variables too, which the roles use on every resolve-by-name step.

All 173 playbook, target and role files pass, and the three failure modes were
each verified by editing a role and watching the gate fail: a module that does
not exist, an option the module does not declare, and a variable nobody
defines.

**A declared option that did nothing.** `ckafka_topic` offers `tags`
("Tags to apply to the topic as a dict, for example `env=prod`. Only applied
at creation.") and no code path read it: a playbook that set tags got a topic
without them, silently. It is sent on create now, in CKafka's own
`Tag`/`TagKey`/`TagValue` shape — the shared `build_sdk_tags` helper sets
`Key`/`Value`, which this API ignores, so the module builds the shape itself.
The same audit found `tse_governance_host_retirement.state`, which offers
`choices: [absent]` and `default: absent`: a constant with nothing to branch
on, and the gate says so rather than demanding a read.

`scripts/check_module_options.py` closes the class: a declared option must be
read somewhere — its name beyond its own declaration in the module, or in a
module helper the module imports, which is how `cos.resolve_appid(module)`
reads `appid` inside `module_utils/cos.py`. Two shapes are deliberately out of
scope: a nested sub-option, because a generic mapper may rename its key
(`mqtt_instance._items` turns `vpc_id` into `VpcId`), and a single-choice
constant. 1,027 modules and 5,711 declared options pass; the `tags` defect was
re-created to watch the gate name it.

**A documented option that did nothing.** `plugins/inventory/tencentcloud_sg.py`
documented `include_sgless` — "whether to include ENIs that carry no matching
security group when `security_group_ids` is empty" — from the day the plugin
was written, and never read it. An inventory plugin accepts any option it
documents, so a user could set it and silently get the default behaviour; no
test executed the plugin either. It is implemented now (the per-group pass
cannot reach an ENI that belongs to no group, which is what the option is for)
and covered by five unit tests, including the "no effect when
`security_group_ids` is set" clause the documentation promises.

The class is closed rather than the instance: `scripts/check_plugin_options.py`
requires every option a lookup or inventory plugin documents — its own and the
ones it inherits from this collection's fragments — to appear in a
`get_option("...")` call. Options from ansible-core's own fragments
(`constructed`, `inventory_cache`) are left alone: `Constructable` and
`Cacheable` read those inside the plugin instance, so they are the framework's
contract rather than the plugin's. The loader's `plugin` key, a lookup's
`_terms`, and `ssm_parameter.with_decryption` (documented as inert, for parity
with `amazon.aws.aws_ssm`) are listed as exemptions with their reasons. Nine
plugins pass; the defect above was re-created to watch the gate fail.

`scripts/check_quality_gates.py` reads the roles from the documentation side
too: a role's README may name only variables the role offers — its
`defaults/main.yml` inputs plus whatever it publishes with
`set_fact`/`register` (documented as `tc_<role>_result`). A README that names
anything else documents a variable a user cannot set and will not receive,
which is how five roles once lost their `region` input: they read it behind
`default(omit)`, and it never appeared in the interface. All 68 roles pass,
and both directions were verified by mutation — inventing a variable in a
README, and renaming a default without touching the README, each fail the
census.

### The coverage floor could not see one untested file

The coverage gate measures `plugins/module_utils` and `plugins/modules`
together and fails below 80. That is a good measure of the whole surface and a
blind one for a single file: a shared helper can arrive with no tests and move
the total by a fraction of a point.

Two were in that state, and both had the same shape — every uncovered line was
a *defensive* branch, the kind the API reaches and a well-formed test payload
never does. `cos_bucket_read.py` sat at 89%: an empty payload reads as absence,
and COS returns a single `DomainRule`/`OriginRule` as a mapping rather than a
list and a single `Domain`/`Param` as a string rather than a list. None of
those coercions had ever run. `monitor.py` was also at 89%, missing its
ambiguous-name guard, both waiter timeouts and the tag ordering in the create
request. They are at 100% and 97% now, and `check_shared_coverage.py` holds
each of the 23 shared files to its own floor so the next one cannot land
untested.

The gate found `module_utils/tencentcloud.py` at 81% on its first run — a file
my own census had missed because I truncated the sorted list with `head`. Its
uncovered branch was the placeholder `TencentCloudSDKException` that exists for
SDK-less environments, which is how the unit suite itself runs.

### `RETURN` is a promise, and now it is checked

A playbook registers a module's result and branches on a key. Nothing compared
that promise with `exit_json`: `validate-modules` checks the *shape* of the
block — an entry has a description, a `returned` and a `type` — and the
integration targets assert the handful of keys they happen to use. Four modules
returned keys nobody was told about, including `cvm_instance`'s `count`,
`instances` and `terminated`, which are the whole point of `exact_count` mode.

`check_return_docs.py` reads both directions: every keyword passed to
`exit_json` must be documented or be one of the keys Ansible adds to every
result, and a documented key the module never returns is reported too. That
second direction is skipped for the 437 modules that splat a mapping, because a
splat carries keys the check cannot read — the check reports what it can see
and says so rather than guessing.

Reading the same claim from the other side also exposed a hole in the attribute
gate: it required the rules to derive an attribute before comparing support, so
a module documenting `diff_mode` while never calling `maybe_diff` was skipped
instead of reported. Three ALB modules were in exactly that state — they build
a diff and never said so — and the hole is closed.

**The samples.** 976 of the 1,027 modules named their return keys and never
showed the shape behind them; the census is 62 now. Two sources closed it, and
they are different on purpose.

*The hand-written modules* have unit tests that already build a payload and
assert on it, so `scripts/add_return_samples.py` runs the module test suite
with a recorder on the harness's `exit_json`, keeps what every module actually
produced, and documents that — minus `None` values and the keys Ansible adds to
every result. 413 modules gained a sample that way. A sample the script wrote
carries a marker comment (YAML drops comments, so the rendered docs are
unchanged) and `--check` re-runs the capture and fails when one stops matching
the payloads its tests produce. Hand-written samples are exempt on purpose:
`vpc` documents the fields the API returns while its unit test stubs six of
them, and a check that called that a defect would be wrong about the
documentation rather than about the code.

*The generated modules* are owned by `generate_info_modules.py`, and the first
attempt at generating their samples was rejected for a reason worth keeping:
walking the SDK response model for `cvm_instance` produced 110 lines of
`"string"` and `0`, longer than the curated sample and saying less. What works
is a narrower claim. The generator already introspects the SDK for its resource
scaffolds, so it now emits the *structure* of the response model — the field
names and their nesting are the API's own, and every value is deliberately
empty (`null`, `[]`), because this repository cannot call the API and inventing
plausible values is how a sample becomes misinformation. 501 modules gained a
block like this one:

```yaml
address_templates:
  description: Matching address templates.
  returned: always
  type: list
  elements: dict
  sample:
    - AddressTemplateName: null
      AddressTemplateId: null
      AddressSet: null
      CreatedTime: null
      UpdatedTime: null
      AddressExtraSet:
        - Address: null
          Description: null
          UpdatedTime: null
      TagSet:
        - Key: null
          Value: null
```

The field list is not hand-maintained: `generate_info_modules.py --check`
re-derives the block from the installed SDK on every CI run, so it cannot drift
from the model it documents — a stronger guarantee than the marker gives the
captured samples, and the reason the generated modules did not simply get
recorded payloads from their own tests (those fixtures assert on a single
`Marker` field, which would have documented nothing).

Three limits are deliberate rather than worked around:

- **only what a test produced is written** for hand-written modules. A
  documented key no payload carried keeps its description and no sample,
  rather than gaining something plausible; two keys are in that state because
  their payload is a base64 blob or a one-line JSON document that cannot be
  wrapped under the 160-character line the pep8 test allows.
- **generated samples carry no values.** A reader learns the field names and
  the nesting, not what a value looks like. That is the honest half of the
  claim, and it is the half a caller needs to write `result.items[0].TagSet`.
- **the 61 that remain** are hand-written modules whose unit tests build a
  private harness (so no payload is captured) and the two blob cases above.
  That is a measurement, not an assumption: running the module test suite with
  the recorder attached shows 57 hand-written modules whose payload never
  passes through a real ``AnsibleModule``, because their test file replaces
  ``AnsibleModule`` with a private double of its own. Those tests do exercise
  the main path -- ``vpc_info`` asserts the paginated payload on it -- but the
  payload is invisible outside the test file, so the module can neither gain a
  captured sample nor benefit from a fix to the shared harness.
  ``scripts/check_quality_gates.py`` freezes the ones that drive ``run_module``
  this way in ``scripts/quality_baselines/private_harness.txt`` (shrink-only),
  and five are migrated as worked examples: ``vpc_info``, ``subnet_info``,
  ``security_group_info``, ``route_table_info``, ``eip_info`` and
  ``cam_role_info`` -- the last two outside the vpc family (three selectors,
  integer pagination, and a client-side id/name filter), so the recipe is not
  one-product luck
  now call ``run``/``module_args``/``AnsibleFailJson`` like every other module
  test, keeping only the SDK injection and the two factory patches their
  modules need. The census fell from 40 to 34 and the sample census with it,
  because each migration makes a payload observable and
  ``add_return_samples.py`` writes it. One thing the migration teaches: the
  fixture has to become realistic at the same time -- ``subnet_info``'s
  ``FakeItem`` returned ``{"Marker": ...}``, which would have been captured as
  the module's documented sample, so it returns ``SubnetId`` now.

### Every module that can delete shows how

270 write modules accept `state: absent` and 70 showed it. The delete example is
the call a reader copies when they want something gone, and the call with the
least room for guessing: which option identifies the resource, and which
create-only parameters the module still demands.

`add_delete_examples.py` writes the other 231 from the module's own code. The
identity is the set of options its lookup helper reads — mapped back through
the call site, because a helper may take `p` or the individual values — plus
whatever its `required_one_of` names, and the values are the ones its create
example already uses. Two details are worth naming, because both were found by
a module coming out wrong:

* A flag the delete path reads but which is not identity comes from the **unit
  test's delete call**, not from the create example. `alb_load_balancer`'s
  create example sets `deletion_protection: true`, and the module refuses to
  delete a protected load balancer; copying that value would have documented a
  call the API rejects. `cbs_auto_snapshot_policy` gets `force_delete: true` the
  same way.
* A create-only payload is never copied. `cdwch_instance`'s create example
  carries a spec name and an inline password; neither appears in its delete
  example, because the lookup does not read them.

Every generated example is validated against its argument spec by
`check_module_examples.py`, which fails on an undeclared option or a missing
required one — so a wrong example cannot ship quietly.

### An id and a name are alternatives, and the docs say so

Thirty-eight core modules accept both an id and a name for the same resource
and documented them as "Existing policy ID." and "Policy name." — two
unrelated-looking options. A reader cannot tell whether both are needed, which
one wins, or whether the name only works at creation.

Both answers are already in the module. The argument spec declares
`required_one_of=[("policy_id", "name")]`, so exactly one must be given, and
the lookup helper tests the id and falls back to the name, so the id wins when
both are given — written either as `not p.get("load_balancer_id")` inside
`run_module` or as a bare `not group_id` in a `find` helper that `run_module`
passes the option to. `enrich_identity_docs.py` reads both and writes:

> Identifies the policy to manage; one of this or `O(name)` is required, and
> the module matches on the id when it is given.

When the fallback cannot be read, the sentence stops after the half the
argument spec proves. Nothing is guessed.

**One thing this got wrong first, and how it was caught.** Both generators were
given an "ownership" rule — a description the generator wrote may be rewritten
by it, so changing the rule updates the text. The identity generator can claim
its sentence, because `one of this or O(` appears in nothing else. The `state`
generator cannot: forty-six hand-written descriptions, including
`cvm_instance`, `cdb_instance` and `key_pair`, open with the same
`C(present) ` the generator writes, so claiming an opening as ownership
flagged 19 curated descriptions for overwriting. The check reports thin
descriptions instead, and the curated text is left alone.

### `state` now says what it does

Sixty-seven core-subset modules described `state` as "Desired state." — a
sentence that is true of every `state` option in every collection, and that
tells a reader nothing they could not read off the two choices underneath.
They now name the calls: `enrich_state_docs.py` reads the module's syntax tree
and writes the sentence from its own code.

It is not a text search. This collection writes the two phases four different
ways — `if state == "absent"` before or after the present path, a bare
`desired_present` flag whose *body* is the present path, a `state == "present"`
guard with the absent path falling past it, and a ternary that picks the call
(`client.Bind if present else client.Unbind`). Each of those was found by a
module coming out wrong in review, and a reading that missed one put a create
call under `absent` or dropped the delete sentence entirely.

Two rules keep it honest. Alternative calls are joined with "or", because
`mariadb_instance` creates with `CreateHourDBInstance` **or** `CreateDBInstance`
depending on the billing mode and listing both as steps would be false. And a
module whose delete path cannot be read is left alone rather than described
without it: a `state` description that never mentions deletion is worse than
the thin one it would replace.

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

### Delete examples, and the 232 that are still missing

The same guard makes delete examples checkable, so 38 write modules that
documented only how to create their resource now document how to delete it.
The identity options come from each module's own delete path rather than from
its create example, which matters in both directions: `alb_load_balancer`
refuses to delete a load balancer whose `deletion_protection` is on, so its
delete example clears it, while `dbbrain_sql_filter` and `cmq_subscription`
mark their create parameters unconditionally required, so those have to be
passed to delete as well. 232 write modules that support deletion still show
only how to create, and that number is a ratchet in
`scripts/check_quality_gates.py` and is printed by every CI run. Generating
the remaining examples was tried and rejected: the identity has to come from
the module's own delete path, because a create example carries payloads a
delete does not need, and mixing a name from one fixture with an id from
another produces a task that finds neither.

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

### The declared SDK range is verified, not asserted

`requirements.txt` advertises `tencentcloud-sdk-python>=3.1.174,<4.0.0`, and
the generated `*_info` specs carry the SDK release they were discovered
against. Both halves of that were wrong at once, and neither guard that
existed could see it:

- the stamp said **3.1.164**, below the floor of the range the project
  declares, so the artifacts were vouched for by a release users are not
  allowed to install. Re-running `scripts/discover_info_specs.py` against
  3.1.174 rewrites that one line and nothing else — 278 specs, byte for byte
  identical — so the artifact was right and only its stamp was stale;
- `scripts/check_sdk_drift.py` compared the stamp with the *installed* SDK,
  and CI installed the stamp, so the comparison could not fail. The range is
  now read from `requirements.txt` and checked in both directions.

The floor itself was never installed by anything, so it was an assertion
rather than a tested claim. `scripts/check_sdk_floor.py` resolves every SDK
reference in `plugins/` — product packages, `*_client` submodules, the
`*Client` class each module instantiates, the request models the auto specs
name, the `RESOURCE_SPECS`-style tables that name the SDK in strings, and the
separate `qcloud_cos` SDK — against the installed release, and fails unless
that release is the declared floor. Run against 3.1.180 it reports exactly
what a newer SDK discovers and the declared floor does not ship at all:
three products (`edgezone`, `databuddy`, `workbuddyenterprise`) whose client
packages are absent from 3.1.174. That is the mechanism by which a module can
be shipped that no user of the documented range can run.

Two censuses of existing debt are also frozen as shrink-only lists
(`scripts/quality_baselines/`) rather than left as bare ceiling numbers: 62
`RETURN` blocks with no `sample` (976 before the samples work above) and 135
core-subset write modules with no integration target. A stock ceiling cannot tell "fixed three, broke three"
apart from "fixed nothing", and it charges a new module for the sins of the
old ones. A module that is not on a list must not have the finding, a listed
module that no longer has it must be delisted (the gate names it, and
`--write-baseline` does the delisting), and the count ceilings stay as the
debt budget so the list cannot simply be extended.

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

### Why the last modules still carry no RETURN sample

Measured, not assumed: running the capture and comparing each unsampled module
against the payload the recorder actually saw splits the remainder in two.

* **29 produce no payload the census can use.** Their tests do run the module
  (24 of them reach `run_module` through the shared harness), so the recorder
  is not attributing those payloads to the module: the census looks a payload
  up by module name, and one captured while a test module ran ends up under a
  name it does not recognise. The follow-up is to record the module an
  `exit_json` call came from -- the calling frame's `__name__` -- rather than
  the test's snapshot, which would let these modules document themselves.
* **5 return a list, not a mapping** (`cam_saml_provider`,
  `cos_bucket_domain_certificate_info`, `cos_bucket_intelligent_tiering_info`,
  `elasticsearch_index`, and one more). The writer only attaches a sample to a
  documented key inside a dict, so a bare-list payload is skipped; the
  follow-up is to attach the list to the module's single documented top-level
  key instead of dropping it.

Neither case is a coverage gap in the ordinary sense -- those modules are
executed and asserted -- so the census is a documentation debt with two known,
enumerated causes rather than an unexplained number.

### The three modules that keep no sample, named

The census prints three names; each has a measured reason, and two of them are
not the writer's problem at all.

* **`organization_member_identity`** -- the only documented entry is
  `identity_ids`, and every payload the tests produce carries it as ``null``
  (twelve captures, all `None`): there is nothing to document yet. The fix
  belongs in the test, which needs a case whose fake response actually has
  members; writing `sample: null` would say less than the key alone does.
* **`cam_saml_provider`**, **`cdb_database_info`** -- the value under the
  remaining entry cannot be rendered inside the 150-character line budget
  without altering it (a folded YAML scalar inserts spaces into a JSON string),
  so they are a reasoned floor rather than a gap. Raising the budget is what
  would make the number smaller, and the budget is a documentation rule.

The recorder must not paper over the first case: a payload list is not a value,
which is exactly what the sample gate caught when the writer tried to attach
one.

### Truthiness versus `is not None`: the sweep behind the diff fix

Fixing `build_diff`'s falsy collapse raised the obvious question -- where else
does a truth test decide whether a value is present? A sweep over
``plugins/module_utils/`` found nine sites of the ``X if X else None`` shape and
classified every one of them, because the answer is not "all of them are bugs":

* **presence of a message, flag, collection or object** -- deliberate and
  correct: an empty error string is no error (``base.py:93``), an
  internet-facing flag (``inventory.py:339``), a pool id or module name
  (``inventory.py:520``, ``inventory.py:784``), an SDK model that is either
  there or not (``monitor.py:26``), a match list (``monitor.py:48``), optional
  filter fragments in a log line (``resolver.py:290-292``), a profile
  (``client.py:130``, ``cos.py:126``) and an empty filter set
  (``resolver.py:287,294,358``).
* **a resource value** -- the defect: ``False``, ``0`` and ``""`` are states a
  resource can hold, and folding them into absence makes ``--diff`` and check
  mode lie. That is what `build_diff` did, and it was the only site in
  ``module_utils`` that treated a value this way.

So the rule is about what is being tested, not about the syntax: truthiness
answers "is there anything to say?", and it is wrong only where the question is
"what is the value?".

### Why there is no gate for that pattern

The obvious follow-up to the sweep -- a check that flags ``X if X else None``
-- was measured before it was written, and the measurement says no:

* across all 1027 modules the shape occurs **zero** times, so such a gate would
  have no true positives to find;
* inside ``module_utils`` it occurs nine times, and every one of them is a
  correct presence test (the table above).

A gate whose only possible findings are nine false positives is the kind that
gets switched off, and a switched-off gate protects nothing. The rule is
written down instead, next to the fix it came from; if the shape ever appears in
a module, the reviewer reading this section has the classification to judge it.

### EXAMPLES consistency: measured clean, so no gate

Two dimensions of EXAMPLES quality that a gate could check were measured
across all 1027 modules before deciding whether to write one:

* a `choices` option given a value outside its choices in an example (templated
  values skipped): **0 findings**;
* an example task passing an option the module does not document: **0
  findings**.

Both are the state a reviewer would hope for, which means a check would have no
true positives to report -- the same reason the truthiness check was not built.
They are recorded here as measurements so the next person does not have to
re-derive them, and so a future regression is recognised as a change from a
clean baseline rather than as an unknown.

(The third obvious dimension -- does an example call its own module, by FQCN,
and only modules that exist -- turned out to be **already gated** by
`scripts/check_module_examples.py`; re-measuring it across 1,639 task actions
found the gate green, with `ansible.builtin.copy` the single legitimate
non-collection action.)

Two more EXAMPLES dimensions were measured later, and these two did **not**
stay measurements:

* a scalar whose YAML type contradicts the option's declared type (unquoted
  `2.1` is a float, not the version string; unquoted
  `1400000000_218695_1590065777` is YAML digit grouping that eats the
  underscores the API expects): **8 findings in 6 modules**, all fixed by
  quoting or by listing the value, and the check added to
  `scripts/check_module_examples.py` as its `types` rule -- its detector
  immediately found a ninth (`dlc_spark_job.role_arn`) that the ad-hoc
  measurement had missed, which is why the gate and not the notebook is the
  source of truth;
* a module re-declaring a doc-fragment option with a *different* type: **1
  finding** (`dlc_spark_job.role_arn: int` shadows the credentials fragment's
  assume-role `role_arn: str`; the runtime lets the module's own spec win, so
  that module cannot be used with an assumed role until the option is renamed
  through a deprecation cycle). Same-type re-declaration is how a module
  overrides a fragment default or description -- 108 sites, harmless. The one
  real shadow is frozen in
  `scripts/quality_baselines/fragment_shadowing.txt` and no new one may
  appear.

### Assertion-less tests: 21 candidates, every one legitimate

A census of all **12,521** unit-test functions looked for tests that never
assert -- no ``assert`` statement, no ``pytest.raises`` guard, no ``assert_*``
helper call in the body. It found **21** candidates across 18 files, and
reading every body found no zombie:

* eleven re-raise tests written as ``try: …; raise AssertionError('expected
  exception'); except Boom: pass`` -- a hand-rolled ``pytest.raises`` for a
  locally defined exception class;
* seven tests whose assertion is that the call returns *without* raising --
  ``_wait`` helpers that would call ``fail_json`` on timeout, validators run
  against a fake module whose ``fail_json`` raises, and a callback armed with
  ``AssertionError`` so the forbidden call fails the test from the inside;
* one YAML-block test that fails via ``pytest.fail`` when a block is missing;
* one parametrized dispatcher (``test_role_task_contract``) whose assertions
  live in the ``_check_*`` helpers it calls.

That is a false-positive rate of 21/21 for the naive detector, so no gate was
written -- the same reasoning as the truthiness sweep. The census is recorded
here so a future *genuine* zombie is recognised as a regression from a
classified baseline.

### Dead helpers: five deleted, three contract-only ones kept on purpose

A census of top-level helpers in every module asked which are called by
anything -- the module itself, its tests, the contract suite. It found five
that nothing reaches: four identical ``_first`` one-liners (``cfs_file_
system``, ``ckafka_topic``, ``gaap_proxy``, ``ssm_parameter``) and
``module_utils/client.py``'s ``sdk_version()``, whose docstring still claimed
``base.exit_json`` called it -- that caller is gone. All five were deleted,
and the census became the ``dead_helper_findings()`` ratchet (0) in
``scripts/check_quality_gates.py``.

The census also surfaced a class worth recording rather than deleting:
``sqlserver_instance.security_groups_request``/``renew_request`` and
``tke_cluster_endpoint.build_status`` are *called by the contract suite*
(which audits their request shapes) but not wired into the modules' run
paths -- post-create security-group and auto-renew reconciliation, and
endpoint-status polling, are scopes the modules do not reconcile today.
Wiring them changes module behaviour, so it stays a product decision; the
gate keeps the helpers alive by definition because the contract suite names
them.

The detector's precision rules were earned the hard way: a plain repo-wide
text search rescues any dead helper whose name coincidentally appears
elsewhere (``_first`` exists as a *local* in a dozen modules, and the census
file's own comments named all four), so references count only in files that
mention the module's own stem, and the census file is excluded from its own
corpus.

### argspec internal consistency: seven dimensions, all clean

The argument spec is the one structure that fails *at runtime, for every
user* when it is wrong, and most of its consistency rules are nobody's gate
(``validate-modules`` reads the documentation; the argspec itself is code).
Seven dimensions were measured across every module whose spec is statically
readable -- **968 of 1027** (the remaining 59 have no options of their own,
an empty ``update({})`` over the shared base):

* ``mutually_exclusive`` / ``required_one_of`` / ``required_together`` /
  ``required_if`` / ``required_by`` naming an option that does not exist:
  **0 findings**;
* ``DOCUMENTATION`` type disagreeing with the argspec type on the module's
  own options: **0 findings**;
* an option whose value *is* a secret (``password``, ``secret_value``,
  ``private_key``, ``secret_key`` and kin) without ``no_log: true``: **0
  findings** -- the naive name match flags 24, all of them names, types or
  flags (``secret_name``, ``rotate_password``, ``reveal_secret_value``,
  ``client_token``), none of them a secret value;
* a ``type: list`` option without ``elements``: **0 findings**;
* an alias colliding with another option's name (an AnsibleModule hard
  error): **0 findings**;
* a ``default`` outside its ``choices``: **0 genuine findings** -- the six
  naive hits are all ``type: list`` options whose default is a list of
  allowed *element* values (``default: [OUTER]`` with
  ``choices: [INNER, OUTER]`` is correct list semantics);
* a ``required: true`` option carrying a ``default``: **0 findings**.

All seven are recorded as measurements, not gates -- a gate whose only
findings are false positives gets switched off, and these populations are
clean. Roles carry no ``meta/argument_specs.yml`` at all (68/68), so that
drift class does not exist; the README is the validated surface and it is
already gated.

### Test-suite hygiene and fragment truthfulness

Four smaller censuses, three recorded as measurements and one that became a
gate:

* **shadowed duplicate definitions** in test files -- a second ``def`` with
  the same name silently discards the first, losing tests without a trace.
  Naive census: 1 hit (``FakeSnapshotClient.snapshots``), which is a
  ``@property`` + setter pair, the correct pattern. Refined census
  (property/setter/deleter excluded): **0 genuine findings**;
* ``time.sleep`` in tests: **0 genuine findings** -- the single match
  *patches sleep out* of a waiter test, which is the correct pattern;
* warning suppression: **no** ``filterwarnings``, ``catch_warnings`` or
  pytest ini filters anywhere -- the suite's warnings run unsuppressed and
  visible;
* **changelog fragment subjects** -- the part of an entry before the first
  `` - `` names what the entry is about, and a snake_case token there must
  resolve to a module, role, script or plugin of the collection. Measured:
  all 88 fragments resolve. This one became a gate in
  ``scripts/check_changelog_fragments.py`` because the failure mode already
  happened once (a fragment named modules from an earlier, wrong census and
  read as fact in the release notes); the allowlist holds exactly one term
  (``no_log``) with its reason.

### Reference integrity: seven more censuses, all clean

A sweep of the places where one file names another, measured before
deciding on gates:

* ``extends_documentation_fragment`` naming a fragment file that does not
  exist (docs would be silently incomplete): **0 findings** across all
  1,027 modules;
* a non-module plugin (``action``, ``callback``, ``connection``,
  ``event_source``, ``filter``, ``inventory``, ``lookup``, ``plugin_utils``)
  no test file references: **0 findings**;
* ``version_added`` hygiene: **0 anomalies** -- 18 distinct values, every one
  a released version except the single anticipatory ``1.5.0`` (116 modules,
  the next release; galaxy and the changelog both sit at 1.4.0);
* the test suite's 38 warnings: **all external** -- ``UserWarning``\ s raised
  by the TencentCloud SDK's own EMR models when tests set those properties,
  nothing raised by collection code;
* CI workflow references to ``scripts/`` and ``tests/`` paths that do not
  exist (a rename would break CI silently): **0 findings**;
* integration target tasks invoking a collection module that does not exist:
  **0 findings** across 262 module references (play ``tasks``/``handlers``
  and ``block``/``rescue``/``always`` descended into, option dicts never
  mistaken for tasks, ``ansible.builtin`` the only other namespace);
* ``RETURN`` keys in both directions -- documented keys the module never
  returns, returned keys nobody documented: **already gated** by
  ``scripts/check_return_docs.py`` (verified while scoping this sweep; not
  re-implemented).

All recorded as measurements; the populations are clean and the one
dimension that needed a gate already had it.

### Mutation spot-check: the suite kills 32 out of 32

A gate counts tests; it cannot tell whether the tests would notice the
module doing the *wrong* thing. That is what mutation testing answers, so a
spot-check ran two mutation classes against samples of the write modules, in
the harness layout (the repository was never touched):

* flip the first ``module.check_mode`` guard to its negation -- 457 write
  modules carry the guard; a 16-module sample, evenly spaced across
  products: **16/16 killed**, every one by assertion failures (2-7 red
  tests each), zero survivors;
* flip the first ``state == "absent"`` comparison -- 339 modules carry one;
  a second independent 16-module sample: **16/16 killed** (6-13 red tests
  each), zero survivors.

32/32 means the dry-run and delete-path tests pin *behaviour*, not just
coverage: invert the guard and the suite goes red everywhere. One
methodology note for the next person: a first run of this spot-check
reported "14/14 killed" that was worthless -- the subprocess had lost
``PYTHONPATH``, every test file errored at collection, and an error is not
an assertion. Kills were only counted when the summary line read
``N failed``; anything else was classified separately.

Two smaller censuses from the same round, both clean: no ``deprecated``
entry has a ``removed_in`` version at or below the current galaxy version
(**0 stale deprecations**), and all **457/457** write modules carry an
entry in the SDK contract suite's request-audit table -- the contract
coverage has no gaps.

### Dry-run assertion strength: 1,110 tests, one genuinely weak

The ``check_mode`` ratchet counts dry-run tests; it cannot tell whether a
dry-run test would notice the module *writing anyway*. A census of all
**1,110** dry-run tests asked which of them assert that no write happened --
the fake client's call list, a negated write-op name, an unchanged state
store, an absent output file, or a mock's ``assert_not_called``. Four
detector passes were needed because the idiom varies per file (call-name
lists, ``_names``/``_ops`` helpers, intermediate ``ops`` variables,
``MagicMock`` side-effect stores, ``pytest.raises`` validators that fail
before any write, and filesystem assertions):

* 1,059 assert the no-write fact directly;
* 12 pin a *validation* path that raises in check mode before any write
  (immutable-drift failures -- correct, the write is unreachable);
* 34 residue were read one by one: 18 assert through intermediate variables
  (``ops = [c for c, _ in fake.calls]``) or state stores, 12 pin validators,
  and **4** remained: two were strong via captured calls my classifier could
  not see, and **two plus one** were genuinely thin:
  ``test_cvm_instance_security_group::test_present_check_mode_bind_only``
  asserted ``changed`` and the "Would bind" message but never that no bind
  call was made, and the no-op dry-run tests of ``cdb_account_privilege`` and
  ``cos_object_sync`` asserted ``changed is False`` with no write assertion.
  All three now assert the no-write fact in their file's own idiom.

No gate was written: the idiom diversity that took four detector passes is
exactly what makes a naive gate cry wolf. The census and its fixes are
recorded here.

A third mutation class extended the spot-check to the generated read-only
modules: emptying the ``items = response.X or []`` extraction in a 16-module
sample of the 63 ``_info`` modules with that shape -- **16/16 killed** by
assertion failures, zero survivors.

A fourth class went after idempotency itself: the codebase's create guard is
``if current is None:`` (214 sites), and flipping the first one in a module
to ``if True:`` makes it *create always*. In a 16-module sample of the 116
write modules carrying the guard, **12 were killed by assertion failures**
(second-run-changed-False and call-count assertions going red) and **4 were
killed by timeout** (dlc_data_engine, dlc_partition_queue, dlc_work_group,
tione_notebook: the module re-creates on every poll, the waiter never
converges, and the suite cannot pass). Zero survivors; the four hang-prone
files were re-verified green after the restore. A timeout is a weaker signal
than an assertion failure -- it costs 180 seconds instead of 0.2 -- so the
protocol counts it separately, never as ``N failed``.

Tally across the four classes: **64/64 mutants neutralised, 60 by
assertions, 4 by non-convergence, 0 survivors**.

The fifth round of the spot-check went after the shared machinery in
``module_utils`` -- one mutant, the whole suite, because every module
depends on these:

* ``build_diff`` returning ``None`` always ("never any drift"): **177 tests
  fail** -- the diff contract is pinned everywhere;
* ``Paginator.fetch_all`` stopping after the first page: **420 tests
  fail** -- multi-page fixtures are widespread, pagination is not
  undertested;
* ``retry_on`` never retrying: **2 tests fail**, both in
  ``test_retries.py`` -- the policy function is pinned directly, and that
  is the right place for it.

But the third one had a shadow: the *wiring* mutant -- ``base.sdk_call``
calling ``invoke()`` directly instead of handing the call to ``retry_on``
-- **survived the entire suite**. The policy was tested, the hand-off was
not (module tests fake the client below the wiring, and the one module
referencing throttling does not exercise it). Two wiring tests in
``test_api_call_trail.py`` now pin it: the default path retries a throttled
error and recovers, and ``retry=False`` never retries. Re-running the
wiring mutant kills exactly the new test and nothing else -- a closed gap
with a named guard.

A second module_utils batch brought a second survivor, and with it the
spot-check's most instructive result so far:

* ``compare_tags`` always reporting equal: **7 tests fail** -- tag drift is
  pinned in every tag-bearing module;
* ``is_idempotent_success`` always false: **2 tests fail** -- delete-not-
  found is pinned;
* ``resolve_one`` querying without its server-side filters: **1 test
  fails** (the fuzzy-noise test), because ``filter_records`` re-checks
  every match client-side -- the server-side filter is documented as a
  narrowing optimisation, and the correctness net below catches its loss;
* ``resolve_all`` querying without filters: **survived the whole suite**.
  Same net, same documented contract -- but no test pinned the filter
  *construction* at all (and ``resolve_all`` has no production caller; it
  is a utility kept for its contract).

Three contract tests in ``test_resolver.py`` now pin the documented
behaviour -- ``resolve_all``/``resolve_one`` pass the id/name/extra filters
to the describe callable, and pass ``None`` when there are no selectors --
and re-running the surviving mutant kills exactly the new test. The lesson
is recorded: when a mutant survives, first check whether it is *equivalent*
(correctness re-checked elsewhere) before calling it a gap; here it was
equivalent for every current caller, and the contract test exists so a
future caller relying on server-side narrowing does not inherit silence.

Two smaller censuses from the same round, both clean: unit tests carry **no
real network imports** (the 544 naive ``requests.`` hits are variables named
``requests``, not the HTTP library -- the one ``from requests`` match is
inside a docstring), and all **1,027/1,027** modules carry the
``if __name__ == "__main__":`` guard.

## Where every quality dimension stands (closing inventory)

One place to audit the work, with the evidence next to each line rather than in
sixty commit messages.

| dimension | state | evidence |
|---|---|---|
| `RETURN` samples | 976 modules unsampled at the start, **2** now | `scripts/add_return_samples.py --check` re-derives all **510** samples; `scripts/quality_baselines/return_samples.txt` explains its own two (values too long for the 150-character budget) |
| module test depth (P0-09) | **1,095 files, none under 80 lines** | `scripts/check_roadmap_status.py`; the roadmap chip is marked done in `docs/panorama.html` |
| modules no test references / no test runs / private doubles | **0 / 0 / 0** | `scripts/check_quality_gates.py`; the three baseline files were deleted once the censuses hit zero |
| SDK floor truthfulness and drift | gated | `scripts/check_sdk_floor.py`, `scripts/check_sdk_drift.py` |
| secrets reaching a log | **0 unguarded, 0 interpolated** | `scripts/check_secret_handling.py` |
| documented options nothing reads (plugins, modules) | **0 findings** | `scripts/check_plugin_options.py`, `scripts/check_module_options.py` |
| role task files and role READMEs | gated | `scripts/check_examples.py` (role tasks), `role_doc_findings()` in `check_quality_gates.py` |
| EXAMPLES consistency (options, choices) | **0 findings, measured** | the measurements written up above |
| EXAMPLES module references (exists, FQCN, self-call) | **gated** | `scripts/check_module_examples.py` (it caught a shipped typo: `tse_governance_aliase_info`) |
| EXAMPLES value types vs declared types | **8+1 found, fixed, gated** | the `types` rule in `scripts/check_module_examples.py`; the YAML digit-grouping case is written up above |
| `RETURN` sample type vs declared type | **1 found, fixed, gated** | `return_sample_type_findings()` in `scripts/check_quality_gates.py` (`ssl_certificate.deploy_record_id` was `str`, the SDK sends an int) |
| module/fragment option shadowing | **1, frozen** | `fragment_shadow_findings()` + `scripts/quality_baselines/fragment_shadowing.txt` (the `dlc_spark_job.role_arn` story is written up above) |
| assertion-less ("zombie") tests | **21 candidates, 0 genuine** | the census written up above |
| dead module helpers | **5 deleted, gated at 0**; 3 contract-only helpers classified and kept | `dead_helper_findings()` in `scripts/check_quality_gates.py`; the contract-only class is written up above |
| argspec internal consistency (7 dimensions) | **0 findings, measured** across 968 statically readable specs | the sweep written up above |
| test-suite hygiene (duplicates, sleeps, warning filters) | **0 genuine findings, measured** | the census written up above |
| changelog fragment subjects resolve to real names | **gated** | `scripts/check_changelog_fragments.py` subject check (the wrong-module fragment failure mode) |
| reference integrity (fragments, plugins, versions, workflows, integration refs) | **0 findings, measured** (7 censuses) | the sweep written up above |
| test-suite strength (mutation spot-check) | **64/64 module mutants + 8/9 module_utils mutants neutralised**; two gaps found (`sdk_call` wiring, `resolve_all` filter contract) and closed with named tests | the protocols and both survivor stories written up above |
| unit-test hermeticity / `__main__` guards | **0 network imports / 1,027 of 1,027** | same round, written up above |
| dry-run assertion strength | **1 genuinely weak in 1,110, fixed** (+2 no-op tests strengthened) | the four-pass census written up above |
| stale deprecations / contract coverage | **0 / 457 of 457** | same round, written up above |
| `--diff` falsy semantics | fixed, with the pattern classified | `module_utils/comparison.py`, its unit test, and the classification above |
| integration targets / undispatched gated targets | **135 / 8, account-dependent** | `scripts/quality_baselines/integration_missing.txt` explains its own number |
| thin option descriptions | **222, product knowledge** | measured and deliberately not automated |
| forum drafts | unposted | no Discourse credentials in this environment |

Four checks were measured and deliberately **not** written, each with the
measurement recorded: the truthiness sweep (nine sites, all correct), the
EXAMPLES options/choices pair (clean), the assertion-less test census (21
candidates, all legitimate patterns), and anything derived from SDK model
*values* (the generator emits structure, not invented values).
