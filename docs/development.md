# Development guide

## Module conventions

- Read-only modules end in `_info`, return `changed=false`, and support check mode.
- Resource modules accept `state: present|absent` and must be idempotent.
- New resource modules subclass `TencentCloudModule` from
  `plugins/module_utils/base.py`, which pre-wires the shared argument spec
  (credentials, retry/waiter parameters), `require_sdk`, `create_credential`,
  `create_client` and `sdk_call` (with the shared retry policy).
  `plugins/module_utils/tencentcloud.py` is a preserved shim for the older
  discovery modules; new code imports from the dedicated modules
  (`client.py`, `base.py`, `comparison.py`, `errors.py`, `paging.py`,
  `retries.py`, `tagging.py`, `waiters.py`).
- API responses use the Tencent Cloud SDK field names. Do not silently rename
  fields until the collection has a documented normalization policy.
- ID-list parameters and API filters are mutually exclusive when the API says so.
- Every module needs request-builder unit tests and an integration target before
  being declared stable.

## Credentials and profiles

- Modules take credentials from the shared argument spec: explicit parameters
  first, then `TENCENTCLOUD_*` environment variables (wired via
  `env_fallback`), then the selected TCCLI profile section of
  `~/.tencentcloud/default.configure` (the `profile` option, or
  `TENCENTCLOUD_PROFILE`). Precedence is param > env > profile; profile data
  is only a fallback and must never crash a module that does not rely on it
  (`client.load_profile` returns `{}` on any read error).
- `client.create_credential` also resolves the region with the same
  precedence and writes it back to `module.params['region']`, so modules
  reading the parameter stay unaware of profiles.
- Setting `role_arn` exchanges the long-lived credential for temporary STS
  credentials via `AssumeRole` before any service client is built.

## Diff mode

- Write modules build their diff with `maybe_diff(module, before, after)`
  from `plugins/module_utils/comparison.py`: `before` is the current remote
  state, `after` the desired state (mirrors `amazon.aws`). The diff is only
  attached in check mode or under `--diff`; in plain runs it is omitted to
  keep the result payload small.
- Unpack with `or {}` so the `diff` key is absent entirely when unwanted:
  `module.exit_json(changed=True, **(maybe_diff(module, before, after) or {}))`.

## Resource resolution

- Look a resource up through `resolver.resolve_one` from
  `plugins/module_utils/resolver.py`, never by taking `XxxSet[0]`. Tencent
  Cloud list filters are substring matches, so `vpc-name=prod` also returns
  `prod-old`; a resolver result is always re-checked client-side.
- The contract: an ID is authoritative (a rename task still finds the
  resource), an exact name wins over a fuzzy one, a single fuzzy candidate
  is accepted for backwards compatibility, and two or more candidates fail
  with `ambiguous=true` plus the candidate list. No selector at all returns
  `None` — it is never a wildcard listing.
- Write the lookup as a `describe(filters)` callable and pass the
  server-side filter names (`name_filters`, `id_filters`) separately;
  `resolver.attach_filters` keeps any scope filter the module already set
  (for example a subnet lookup's `vpc-id`).
- Product-specific identity that is not an ID, a name or a tag goes through
  `extra_match` (an ENI's `SubnetId`, a Direct Connect tunnel's
  `DirectConnectId`). Pass it only when the task actually supplied that
  scope, otherwise a lookup with no selector would match everything.
- Paginated `Describe*` calls collect every page inside `describe` and return
  the full list; the resolver does the matching.
- Every lookup in a resource family is pinned by one contract test — see
  `tests/unit/plugins/modules/test_resource_family_resolution.py`. Adding a
  module to a family means adding it to that table, not writing a new set of
  near-duplicate tests.

## Lifecycle semantics

- Report SDK failures with `lifecycle.fail_from_sdk_error(module, exc,
  "Operation")` so every module emits the same envelope (`msg`, `error`,
  `error_code`, `error_kind`, `request_id`, `operation`) with credentials
  redacted.
- Lookups that may legitimately find nothing wrap in
  `lifecycle.missing_as_none`; deletes use `lifecycle.delete_resource`, which
  treats an already-absent resource as unchanged instead of an error.
  Resources with a recycle bin (CDB, Redis, MongoDB, CVM) use
  `lifecycle.soft_delete(isolate, purge, force=...)`.
- Compute the change set once with `lifecycle.plan_changes(current, desired)`
  and reuse it for both the check-mode preview and the real run. `None` in
  `desired` means "this task does not manage the field".
- Immutable drift fails through `lifecycle.require_immutable_unchanged`;
  async work is polled by `plugins/module_utils/waiters.py`.

## Unit tests

- New write modules must have run_module-level main-path tests using the
  shared harness in `tests/unit/plugins/modules/harness.py`, in addition to
  request-builder tests. See `test_vpc_main.py` for the pattern.
- The harness injects arguments through `basic._ANSIBLE_ARGS`
  (`harness.module_args(...)`; `_ansible_check_mode=True` and
  `_ansible_diff=True` enable check/diff mode) and monkeypatches
  `exit_json`/`fail_json` to raise `AnsibleExitJson`/`AnsibleFailJson`.
  `harness.run(module.run_module)` returns the `exit_json` payload.
- `AnsibleExitJson` inherits `SystemExit`, not `Exception`, so a module's
  blanket `except Exception` cannot swallow the test exit (mirroring the real
  `exit_json`, which exits the process). Catch it via `harness.run`, never
  with `except Exception`.
- The SDK is not installed in the unit-test environment: monkeypatch
  `TencentCloudModule.require_sdk` (no-op), the module's `_load_*` function
  (returning `harness.FakeModels` and a fake client module), and
  `TencentCloudModule.create_client` (returning a fake client). Use
  `harness.FakeResource` for SDK resource objects (attribute access plus
  `_serialize`). No real SDK imports under `tests/unit`.

## Generated `_info` modules

- `scripts/generate_info_modules.py` renders read-only `_info` modules from
  the hand-curated `SPECS` table (SDK field names verified by introspection).
  Generated files carry a `# Generated by ...` marker: never hand-edit them;
  extend `SPECS` and regenerate instead.
- The generator is re-runnable and idempotent. CI runs it with `--check`
  (`.github/workflows/ci.yml`) and fails on stale generated modules, so
  re-run it before committing spec changes.
- Resource (write) modules are scaffolded, not generated end-to-end:
  idempotency, drift comparison and required-field constraints are
  per-resource decisions the SDK request models do not encode. Add a
  curated `RESOURCE_SPECS` entry (module, service package, identity
  options, create/update/delete + identify actions) and run
  `python scripts/generate_info_modules.py --resource <module>` to render
  the module boilerplate — argument spec and request builders introspected
  from the SDK models — into `plugins/modules/<module>.py`.
- Scaffolding is write-once: an existing module file is never overwritten,
  so a scaffolded module can be finished by hand and stays stable across
  generator runs. `--resources --check` verifies every `RESOURCE_SPECS`
  entry against the installed SDK (CI) and reports missing scaffolds;
  `--print` shows the render without writing.
- The generated `DOCUMENTATION` mirrors the hand-written module conventions:
  identity options are `required: true` and written unconditionally to the
  request, optional fields are guarded with `if params[...] is not None`,
  nested API objects map to `type: dict` with a comment asking the
  developer to model their sub-options, and the shared
  `retries`/`waiter_*`/`user_agent` parameters are documented so
  validate-modules accepts the module.

## Non-API-3.0 services

- Services outside the API 3.0 family get a dedicated helper layer in
  `plugins/module_utils/`, mirroring `client.py`/`errors.py`. COS is the
  example: `plugins/module_utils/cos.py` wraps the `qcloud_cos` SDK
  (`cos-python-sdk-v5`), centralising `CosConfig`/`CosS3Client` construction,
  AppId resolution (`resolve_appid`, via STS `GetCallerIdentity`), the
  `<name>-<appid>` bucket addressing, and COS-specific error classification
  (`get_error_code`/`get_status_code`/`get_request_id` accessors instead of
  the API 3.0 `get_code`).
- Keep the SDK import lazy with a `HAS_*_SDK` flag so `module_utils` stays
  importable without the SDK (unit tests, `ansible-doc`).

## Action plugins

- Action plugins (`plugins/action/`) run on the controller, in the task
  process, and are the only plugin type that can invoke *another module*:
  `self._execute_module(module_name=..., module_args=..., task_vars=...)`
  runs a module and returns its result dict. Reach for one when a task needs
  a second module call, must choose between modules at runtime, or must run
  entirely controller-side. See `plugins/action/tc_wait.py`.
- Declare `_VALID_ARGS` as a `frozenset` of the option names. ansible-core
  then rejects an unknown task option before `run()` is entered; without it a
  typo'd option is silently ignored.
- `super().run(tmp, task_vars)` returns `{}` — it does not seed `changed` or
  `failed`. Start from it and set both explicitly in every return path.
- The base class defaults are already right for a controller-side plugin:
  `TRANSFERS_FILES = False` (nothing is shipped to the target, so
  `_early_needs_tmp_path()` stays false), `_supports_check_mode = True` and
  `_supports_async = False` (the base `run()` raises on `async`). Override only
  to differ from those.
- Because `_supports_check_mode` is `True`, `run()` is entered in check mode:
  handle it there — observe once, then report without acting or polling.
- Fail through `AnsibleActionFail(msg, result=...)`. The `result` payload
  lands on `excinfo.value.result` and is the only way to attach structured
  detail to a controller-side failure — there is no `module.fail_json` here.
- An action plugin resolves no credentials of its own. Either forward `args`
  into the module it invokes (which applies its own `TENCENTCLOUD_*`
  fallbacks) or let that module's `env:` fallbacks do the work.
- Never hand-roll a poll loop: use `plugin_utils.polling.poll_until`, which
  counts the budget as the delays actually slept.
- **Action plugins are invisible to `ansible-doc`.** `action` is not in
  ansible-test's `DOCUMENTABLE_PLUGINS`, and `ansible-doc -t action` is
  rejected even on 2.21, so the DOCUMENTATION block in the file is read by
  source reviewers only. The `action-plugin-docs` sanity test therefore
  *requires a matching `plugins/modules/<name>.py`* to carry user-facing docs.
  A plugin that cannot be a module — because its whole job is to invoke other
  modules — takes an `action-plugin-docs` entry in `tests/sanity/ignore-2.*.txt`
  instead of a stub module, which would otherwise count as a write module in
  `scripts/audit_info_coverage.py` and distort the module inventory.

## Shared helpers and `plugin_utils`

- Implementations go in `plugins/module_utils/`. `plugins/plugin_utils/`
  re-exports the ones non-module plugins need; it holds no logic of its own.
- The direction is enforced, not stylistic. ansible-test's `import` test runs
  modules and `module_utils` under a restricted loader whose only permitted
  collection namespace is `plugins.module_utils`, so
  `from ...plugins.plugin_utils.x import y` **fails the sanity test** for every
  module that transitively reaches it. Putting an implementation in
  `plugin_utils` and importing it from `module_utils` breaks the whole tree —
  `ansible-test sanity --test import` reported 881 errors that way.
- So the order is `module_utils` (implementations) → `plugin_utils`
  (re-exports) → non-module plugins (action / lookup / inventory / connection /
  event_source). The reverse never.
- Do not re-export module globals (constants, file paths). A re-exported
  constant is a separate binding: `monkeypatch.setattr(shim, "PROFILE_FILE",
  ...)` would silently not affect the function that reads it. Re-export
  callables only, and patch the defining module in tests.
- A shim is worth a two-line test asserting identity
  (`plugin_utils.paging.Paginator is module_utils.paging.Paginator`) and that
  nothing else was re-exported, so it cannot quietly grow into a second
  implementation. See `tests/unit/plugins/plugin_utils/`.
- `plugins/plugin_utils/README.md` and `plugins/module_utils/README.md` carry
  the full file-by-file dependency map.

## Lookup and inventory plugins

- Lookup (`plugins/lookup/`) and inventory (`plugins/inventory/`) plugins
  have no `AnsibleModule`: they build SDK clients inline (credential +
  `HttpProfile`/`ClientProfile` + client class), take options via
  `set_options`/`get_option` with `env:` fallbacks declared in
  DOCUMENTATION, and raise `AnsibleError` on failure. See
  `plugins/lookup/sts_caller_identity.py` and
  `plugins/inventory/tencentcloud_cvm.py`.
- Options are parsed from lookup terms with `parse_kv`; the SDK import is
  guarded by `HAS_TENCENTCLOUD_SDK`.
- Inventory plugins paginate through `plugin_utils.paging.Paginator` and
  extend `BaseInventoryPlugin` with `Constructable` and `Cacheable`
  (`plugins/inventory/tencentcloud_clb.py` walks listeners/backends,
  `tencentcloud_sg.py` deduplicates hosts across security groups).

## Connection plugins

- Connection plugins (`plugins/connection/`) run without a shell or module
  runtime, so they must never import Ansible module machinery. Credentials
  are resolved through `plugin_utils.profile.load_profile` via a thin
  `_OptionAdapter` that exposes connection options as module-like `params`
  (see `plugins/connection/tat.py`).
- Never call `super().exec_command/put_file/fetch_file`: the base class
  methods are abstract in ansible-core and raise. Implement each method
  fully.
- Every command is stateless; `exec_command` returns
  `(rc, stdout, stderr)` and must cope with a None `in_data` (pipelining is
  disabled: `has_pipelining = False`).

## Event source plugins

- Event-Driven Ansible sources (`plugins/event_source/`) implement
  `async def main(queue, args)`. Keep blocking SDK calls in
  `asyncio.to_thread`; resolve credentials from args with
  `TENCENTCLOUD_*` environment fallbacks; yield an error event (not an
  exception) on transient API failures so the source stays alive.
- Each source ships a standalone `__main__` runner for manual testing.
  See `plugins/event_source/cls_topic.py` and `cmq_queue.py`.

## Module tiers

- `plugins/modules/*_info.py` are generated (see below); every other module
  is core and must be listed in `CORE_MODULES` in
  `scripts/check_module_tiers.py`. `python scripts/check_module_tiers.py --check`
  fails on any unclassified module, and CI enforces it — a hand-written
  module can never be silently overwritten by the generator. See
  `docs/module_tiers.md`.

When modules or roles change, run
`python scripts/generate_product_capabilities.py`. CI checks that the
product-level capability matrix is current.

## Contract tests

- New write modules must register their request builders in
  `tests/contract/test_sdk_contracts.py`: a `WRITE_MODULE_BUILDERS` entry
  plus a `test_<module>()` function that runs against the real Tencent Cloud
  SDK classes in CI. The contract suite also enforces the coverage
  threshold (`--cov-fail-under`; current gate 80, set in
  `.github/workflows/ci.yml`).

## Local collection layout

`ansible-test` requires the checkout to appear below
`ansible_collections/susunola/tencentcloud`. Clone it into that layout or copy
the tree there before running tests:

```bash
mkdir -p /tmp/acol/ansible_collections/susunola/tencentcloud
rsync -a --exclude .git ./ /tmp/acol/ansible_collections/susunola/tencentcloud/
cd /tmp/acol/ansible_collections/susunola/tencentcloud && ansible-test sanity --python 3.13
```

A **symlink** into that layout does not work: `ansible-test` resolves the
working directory with `os.getcwd()`, so it sees the real path and aborts with
"must be within the source tree being tested". Copy instead, and re-copy after
edits.

## Adding a service

1. Verify request types and limits in the official Tencent Cloud API docs,
   and introspect the installed `tencentcloud-sdk-python-<service>` package
   for exact field names — never guess.
2. Add the minimum SDK product dependency if dependencies are split later.
3. For read-only coverage, add a `SPECS` entry to
   `scripts/generate_info_modules.py` and regenerate; only hand-write an
   `_info` module when the API shape does not fit the generator.
4. Add state-changing modules (subclassing `TencentCloudModule`) with
   check-mode diff calculation via `maybe_diff`.
5. Add run_module-level harness tests and request-builder unit tests; add
   integration tests using credentials from environment variables.
6. Add a changelog fragment under `changelogs/fragments`.
