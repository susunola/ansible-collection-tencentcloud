# Deprecation and removal policy

This collection follows the Ansible community deprecation conventions. A
module, plugin, option or return value is never removed without a warning
period, and every deprecation names its replacement.

## When to deprecate

Deprecate only for a real reason: a renamed module whose old name still
ships, an option replaced by a better-shaped one, or a capability that
moved to another module. Do not deprecate speculatively; an unused
deprecation is warning noise for users.

## Lifecycle

1. **Deprecation release**: the feature keeps working unchanged, but using
   it emits a warning. The deprecation ships in a minor release.
2. **Warning period**: the deprecated feature stays available for at least
   one full major release series (see docs/reliability-policy.md).
3. **Removal**: the feature is removed in a later major release, with a
   `removed_features` changelog entry.

## How to deprecate a module or plugin

Three places change together:

1. `meta/runtime.yml` — add a `plugin_routing.deprecation` entry:

   ```yaml
   plugin_routing:
     modules:
       old_module_name:
         deprecation:
           removal_version: 2.0.0
           warning_text: Use susunola.tencentcloud.new_module_name instead.
   ```

   (For a pure rename prefer `redirect` instead of `deprecation` when the
   old name should keep working silently as an alias.)

2. The module's `DOCUMENTATION` — add a `deprecated` block:

   ```yaml
   deprecated:
     removed_in: '"2.0.0"'
     why: The functionality moved to a better-named module.
     alternative: Use M(susunola.tencentcloud.new_module_name) instead.
   ```

3. A changelog fragment under `changelogs/fragments/`:

   ```yaml
   deprecated_features:
     - "old_module_name - deprecated in favor of new_module_name; the old module is removed in 2.0.0."
   ```

## How to deprecate an option or return value

- Options: add `deprecated:` sub-keys (`removed_in`, `why`, `alternative`)
  to the option's argument_spec entry (ansible-core warns at runtime) and
  mirror them in the option's DOCUMENTATION entry.
- Return values: document the deprecation in the RETURN entry and announce
  it in a `deprecated_features` changelog fragment.

## Verification

- `ansible-test sanity --test validate-modules` checks the deprecated
  blocks parse and the removal versions are valid.
- The deprecated path keeps its unit tests until removal; add one test
  asserting the warning/fallback behavior where the harness allows it.
