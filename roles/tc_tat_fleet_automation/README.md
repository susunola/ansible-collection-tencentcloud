# tc_tat_fleet_automation

Creates one reusable TAT command, executes declared immediate fleet operations,
and reconciles scheduled invokers. Immediate invocations are action semantics:
each role run starts them again. Keep `tc_tat_fleet_automation_invocations`
empty for schedule-only idempotent playbooks.

Tasks containing scripts, parameters or output use `no_log: true`. Teardown
requires `tc_tat_fleet_automation_allow_destroy: true` and removes schedules
before the reusable command.

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: susunola.tencentcloud.tc_tat_fleet_automation
      vars:
        tc_tat_fleet_automation_command:
          name: report-disk-usage
          content: df -h
          username: deploy
        tc_tat_fleet_automation_invocations:
          - instance_ids: [ins-xxxxxxxx]
        tc_tat_fleet_automation_schedules:
          - name: nightly-disk-report
            instance_ids: [ins-xxxxxxxx]
            policy: RECURRENCE
            recurrence: 0 2 * * *
```
