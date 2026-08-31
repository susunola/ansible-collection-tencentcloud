# tc_ssm_secret_governance

Creates and governs an SSM secret, its explicitly named immutable versions and,
for supported managed-product secrets, its automatic rotation schedule. Secret
tasks and published facts use `no_log: true`; callers should apply the same rule
to play-level diagnostics and persisted artifacts.

Destruction is guarded by `tc_ssm_secret_governance_allow_destroy: true` and
schedules deletion using the recovery window from `secret.recovery_window_days`.
Setting that value to `0` requests immediate, irreversible deletion.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_ssm_secret_governance
      vars:
        tc_ssm_secret_governance_secret:
          secret_name: prod-database
          description: Production database credentials
          initial_version_id: bootstrap
          initial_secret_string: '{{ vault_bootstrap_credentials }}'
          recovery_window_days: 14
        tc_ssm_secret_governance_versions:
          - version_id: release-2026-09
            secret_string: '{{ vault_database_credentials }}'
```
